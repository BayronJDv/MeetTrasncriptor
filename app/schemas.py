"""Esquemas Pydantic para la API."""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


# ---------- ajustes ----------

class AsrSettings(BaseModel):
    model: str = "small"
    language: str = "es"
    device: Literal["cpu", "cuda"] = "cpu"
    compute_type: Literal["int8", "float16", "float32"] = "int8"
    batch_size: int = Field(default=8, ge=1, le=64)
    chunk_minutes: int = Field(default=5, ge=1, le=30)


class DiarSettings(BaseModel):
    device: Literal["auto", "cpu", "cuda"] = "auto"
    hf_token: str = ""
    min_speakers: Optional[int] = Field(default=None, ge=1, le=20)
    max_speakers: Optional[int] = Field(default=None, ge=1, le=20)
    clips_per_speaker: int = Field(default=4, ge=1, le=10)


class LlmSettings(BaseModel):
    provider: Literal["groq", "gemini", "openrouter", "ollama", "custom"] = "groq"
    api_key: str = ""
    model: str = "llama-3.3-70b-versatile"
    base_url: str = ""
    temperature: float = Field(default=0.2, ge=0, le=2)
    window_minutes: int = Field(default=10, ge=2, le=60)
    concurrency: int = Field(default=2, ge=1, le=8)
    max_retries: int = Field(default=4, ge=0, le=10)


class ReportSettings(BaseModel):
    export_format: Literal["docx", "md"] = "docx"


class SettingsPatch(BaseModel):
    asr: Optional[AsrSettings] = None
    diar: Optional[DiarSettings] = None
    llm: Optional[LlmSettings] = None
    report: Optional[ReportSettings] = None


# ---------- hablantes ----------

class SpeakerRename(BaseModel):
    speaker_id: str
    name: Optional[str] = None


class SegmentPatch(BaseModel):
    text: Optional[str] = None
    speaker: Optional[str] = None


# ---------- revisión IA ----------

class SuggestionUpdate(BaseModel):
    status: Literal["pending", "accepted", "rejected", "edited"]
    replacement: Optional[str] = None


# ---------- reunión ----------

class MeetingSection(BaseModel):
    id: str
    type: Literal["tema", "decision", "votacion", "compromiso", "conclusion", "otro"] = "tema"
    title: str = ""
    start: Optional[float] = None
    end: Optional[float] = None
    summary: str = ""
    items: list[str] = Field(default_factory=list)


class MeetingPatch(BaseModel):
    sections: list[MeetingSection]


# ---------- informe ----------

class ReportGenerate(BaseModel):
    template_name: Optional[str] = None
    instructions: str = ""
    include_meeting: bool = True


class ReportSave(BaseModel):
    markdown: str
