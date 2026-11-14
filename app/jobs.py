"""Cola de trabajos pesados (un solo worker) + bus de eventos SSE para progreso en vivo."""
from __future__ import annotations

import asyncio
import json
import queue
import threading
import time
import traceback
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable

from . import config


class JobCancelled(Exception):
    pass


@dataclass
class Job:
    id: str
    project_id: str
    kind: str
    status: str = "queued"  # queued | running | done | error | cancelled
    stage: str = ""
    progress: float = 0.0
    detail: str = ""
    error: str | None = None
    created_at: float = field(default_factory=time.time)
    started_at: float | None = None
    finished_at: float | None = None
    cancel_event: threading.Event = field(default_factory=threading.Event)
    log: list[str] = field(default_factory=list)

    def snapshot(self) -> dict:
        return {
            "id": self.id,
            "project_id": self.project_id,
            "kind": self.kind,
            "status": self.status,
            "stage": self.stage,
            "progress": round(self.progress, 1),
            "detail": self.detail,
            "error": self.error,
            "log": self.log[-30:],
        }

    def check_cancel(self) -> None:
        if self.cancel_event.is_set():
            raise JobCancelled()

    def log_line(self, manager: "JobManager", line: str) -> None:
        self.log.append(line)
        if len(self.log) > 200:
            del self.log[:-200]
        manager.update(self)


class JobManager:
    """Un worker serial: solo un trabajo pesado a la vez (protege la RAM)."""

    def __init__(self) -> None:
        self._q: queue.Queue[tuple[Job, Callable[[Job], None]]] = queue.Queue()
        self.jobs: dict[str, Job] = {}
        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._subs: dict[str, set[asyncio.Queue]] = {}
        self._lock = threading.Lock()

    # ---- ciclo de vida ----

    def start(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop
        if self._thread is None or not self._thread.is_alive():
            self._thread = threading.Thread(target=self._worker, name="job-worker", daemon=True)
            self._thread.start()

    def submit(self, kind: str, project_id: str, fn: Callable[[Job], None]) -> Job:
        for job in self.jobs.values():
            if (
                job.project_id == project_id
                and job.status in ("queued", "running")
            ):
                raise RuntimeError(f"El proyecto ya tiene un trabajo en curso ({job.kind})")
        job = Job(id=uuid.uuid4().hex[:10], project_id=project_id, kind=kind)
        self.jobs[job.id] = job
        self._persist(job)
        self._q.put((job, fn))
        self._publish(job.project_id, {"type": "job", "job": job.snapshot()})
        return job

    def cancel(self, job_id: str) -> bool:
        job = self.jobs.get(job_id)
        if job and job.status in ("queued", "running"):
            job.cancel_event.set()
            if job.status == "queued":
                job.status = "cancelled"
                job.finished_at = time.time()
                self._persist(job)
                self._publish(job.project_id, {"type": "job", "job": job.snapshot()})
            return True
        return False

    def running_for_project(self, project_id: str) -> Job | None:
        for job in reversed(list(self.jobs.values())):
            if job.project_id == project_id and job.status in ("queued", "running"):
                return job
        return None

    def last_job(self, project_id: str) -> Job | None:
        for job in reversed(list(self.jobs.values())):
            if job.project_id == project_id:
                return job
        return None

    def get(self, job_id: str) -> Job | None:
        return self.jobs.get(job_id)

    # ---- ejecución ----

    def _worker(self) -> None:
        while True:
            job, fn = self._q.get()
            job.status = "running"
            job.started_at = time.time()
            self._publish(job.project_id, {"type": "job", "job": job.snapshot()})
            try:
                fn(job)
            except JobCancelled:
                job.status = "cancelled"
                job.detail = "Cancelado por el usuario"
            except Exception as exc:  # noqa: BLE001
                job.status = "error"
                job.error = f"{type(exc).__name__}: {exc}"
                job.log_line(self, f"ERROR: {job.error}")
                traceback.print_exc()
            else:
                job.status = "done"
                job.progress = 100.0
            job.finished_at = time.time()
            self._persist(job)
            self._publish(job.project_id, {"type": "job", "job": job.snapshot()})

    def _persist(self, job: Job) -> None:
        try:
            config.save_json(job.project_id, "job.json", job.snapshot())
        except OSError:
            pass

    # ---- progreso ----

    def update(
        self,
        job: Job,
        stage: str | None = None,
        progress: float | None = None,
        detail: str | None = None,
    ) -> None:
        if stage is not None:
            job.stage = stage
        if progress is not None:
            job.progress = max(0.0, min(100.0, float(progress)))
        if detail is not None:
            job.detail = detail
        self._persist(job)
        self._publish(job.project_id, {"type": "job", "job": job.snapshot()})

    # ---- SSE ----

    def subscribe(self, project_id: str) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=200)
        with self._lock:
            self._subs.setdefault(project_id, set()).add(q)
        # estado actual inmediato
        job = self.last_job(project_id)
        if job:
            q.put_nowait({"type": "job", "job": job.snapshot()})
        return q

    def unsubscribe(self, project_id: str, q: asyncio.Queue) -> None:
        with self._lock:
            self._subs.get(project_id, set()).discard(q)

    def _publish(self, project_id: str, event: dict) -> None:
        with self._lock:
            subs = list(self._subs.get(project_id, ()))
        if not subs or self._loop is None:
            return
        payload = json.dumps(event, ensure_ascii=False, default=str)
        for q in subs:
            try:
                self._loop.call_soon_threadsafe(self._safe_put, q, payload)
            except RuntimeError:
                pass

    @staticmethod
    def _safe_put(q: asyncio.Queue, payload: str) -> None:
        try:
            q.put_nowait(payload)
        except asyncio.QueueFull:
            pass


manager = JobManager()
