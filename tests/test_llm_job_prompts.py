import json

from app import config
from app.jobs import Job, manager
from app.services.llm import meeting, prompts, report, review


TRANSCRIPT = {
    "segments": [{"id": "s1", "start": 0, "end": 5, "text": "texto de prueba", "speaker": "sp1"}],
    "speakers": [{"id": "sp1", "name": "Ana"}],
}


class FakeLlmClient:
    instances = []

    def __init__(self, overrides=None):
        self.overrides = overrides
        self.calls = []
        self.model = "fake-model"
        self.instances.append(self)

    def chat_json(self, messages, max_tokens=None):
        self.calls.append(messages)
        self.messages = messages
        if self.overrides == "meeting_1":
            return {"partes": [{"tipo": "tema", "titulo": "Tema", "inicio": 0, "fin": 5, "resumen": "Resumen", "items": []}]}
        if self.overrides == "meeting_2":
            return {"secciones": []}
        if self.overrides == "report_1":
            return {"notes": "notas sintéticas"}
        if self.overrides == "report_2":
            return {"markdown": "# Informe"}
        return {"sugerencias": []}


def _run_jobs(monkeypatch, tmp_path, configured_prompts=None):
    saved = {}
    FakeLlmClient.instances = []
    monkeypatch.setattr(review, "LlmClient", FakeLlmClient)
    monkeypatch.setattr(meeting, "LlmClient", FakeLlmClient)
    monkeypatch.setattr(report, "LlmClient", FakeLlmClient)
    monkeypatch.setattr(config, "load_config", lambda: {
        "llm": {"window_minutes": 10, "concurrency": 1},
        "advanced": config.DEFAULT_CONFIG["advanced"],
        "prompts": configured_prompts or {},
    })
    monkeypatch.setattr(config, "load_json", lambda project_id, name: {
        "transcript.json": TRANSCRIPT,
        "review.json": None,
        "meeting.json": None,
        "report_work.json": None,
    }.get(name))
    monkeypatch.setattr(config, "save_json", lambda project_id, name, value: saved.__setitem__(name, value))
    monkeypatch.setattr(config, "save_meta", lambda *args, **kwargs: None)
    monkeypatch.setattr(config, "project_dir", lambda project_id: tmp_path)
    monkeypatch.setattr(manager, "update", lambda *args, **kwargs: None)

    review.run_review_job("project", Job("review-id", "project", "review"))
    meeting.run_meeting_job("project", Job("meeting-id", "project", "meeting"))
    report.run_report_job("project", Job("report-id", "project", "report"), None, "Indicaciones", False)
    return FakeLlmClient.instances, saved


def test_jobs_send_default_prompts_identical_to_legacy_render(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "load_json", lambda project_id, name: {
        "transcript.json": TRANSCRIPT,
        "review.json": None,
        "meeting.json": None,
        "report_work.json": None,
    }.get(name))
    clients, saved = _run_jobs(monkeypatch, tmp_path)
    by_task = {client.overrides: client for client in clients}
    payload = review._window_payload(TRANSCRIPT["segments"], {"sp1": "Ana"})
    compact = [{"tipo": "tema", "titulo": "Tema", "inicio": 0, "fin": 5, "resumen": "Resumen", "items": []}]
    expected_users = {
        "review": prompts.DEFAULT_PROMPTS["review_user"]["user"].format(segments=payload, max_suggestions=10),
        "meeting_1": prompts.DEFAULT_PROMPTS["meeting_1"]["user"].format(win_lo=0 / 60, win_hi=5 / 60, segments=payload),
        "meeting_2": prompts.DEFAULT_PROMPTS["meeting_2"]["user"].format(parts=json.dumps(compact, ensure_ascii=False)),
        "report_1": prompts.DEFAULT_PROMPTS["report_1"]["user"].format(win_lo=0 / 60, win_hi=5 / 60, segments=payload),
        "report_2": prompts.DEFAULT_PROMPTS["report_2"]["user"].format(
            template_block="", meeting_block="", notes="[min 0–0]\nnotas sintéticas",
            instructions_block="INDICACIONES ADICIONALES DEL USUARIO:\nIndicaciones\n",
        ),
    }
    for task, expected in expected_users.items():
        messages = by_task[task].messages
        assert messages[0]["content"] == prompts.DEFAULT_PROMPTS[f"{task}_system"]["system"]
        assert messages[1]["content"] == expected

    assert set(saved["review.json"]) == {"status", "suggestions", "processed_windows"}
    assert set(saved["meeting.json"]) == {"status", "sections"}
    assert saved["report_work.json"]["notes"][0]["notes"] == "notas sintéticas"
    assert set(saved["informe.md.json"]) == {"markdown"}
    assert saved["informe.md.json"]["markdown"] == "# Informe"


def test_review_job_uses_prompt_edited_in_config(monkeypatch, tmp_path):
    clients, _ = _run_jobs(
        monkeypatch,
        tmp_path,
        {"review_user": {"system": "", "user": "PROMPT EDITADO {segments} / {max_suggestions}"}},
    )

    review_client = next(client for client in clients if client.overrides == "review")
    assert review_client.messages[1]["content"] == "PROMPT EDITADO " + review._window_payload(
        TRANSCRIPT["segments"], {"sp1": "Ana"}
    ) + " / 10"
