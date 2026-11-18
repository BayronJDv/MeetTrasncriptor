"""Esquemas Pydantic para la API."""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


# ---------- ajustes ----------

class AsrSettings(BaseModel):
    engine: str = "whisperx"
    options: dict[str, dict[str, Any]] = Field(default_factory=dict)
    model: str = "small"
    language: str = "es"
    device: Literal["cpu", "cuda"] = "cpu"
    compute_type: Literal["int8", "float16", "float32"] = "int8"
    batch_size: int = Field(default=8, ge=1, le=64)
    chunk_minutes: int = Field(default=5, ge=1, le=30)


class DiarSettings(BaseModel):
    engine: str = "pyannote"
    options: dict[str, dict[str, Any]] = Field(default_factory=dict)
    device: Literal["auto", "cpu", "cuda"] = "auto"
    hf_token: str = ""
    min_speakers: Optional[int] = Field(default=None, ge=1, le=20)
    max_speakers: Optional[int] = Field(default=None, ge=1, le=20)
    clips_per_speaker: int = Field(default=4, ge=1, le=10)


class LlmTaskSettings(BaseModel):
    model: Optional[str] = None
    max_tokens: Optional[int] = Field(default=None, ge=1)
    timeout: Optional[int] = Field(default=None, ge=1)


class PromptSettings(BaseModel):
    system: Optional[str] = None
    user: Optional[str] = None


class LlmSettings(BaseModel):
    provider: Literal["groq", "gemini", "openrouter", "ollama", "custom"] = "groq"
    api_key: str = ""
    model: str = "openai/gpt-oss-120b"
    base_url: str = ""
    temperature: float = Field(default=0.2, ge=0, le=2)
    window_minutes: int = Field(default=10, ge=2, le=60)
    concurrency: int = Field(default=2, ge=1, le=8)
    max_retries: int = Field(default=4, ge=0, le=10)
    tasks: Optional[dict[str, LlmTaskSettings]] = None


class ReportSettings(BaseModel):
    export_format: Literal["docx", "md"] = "docx"


class AdvancedSettings(BaseModel):
    max_suggestions: int = Field(default=10, ge=1)
    report_template_max_chars: int = Field(default=12000, ge=1)
    report_meeting_max_chars: int = Field(default=6000, ge=1)
    report_instructions_max_chars: int = Field(default=4000, ge=1)
    report_notes_max_chars: int = Field(default=120000, ge=1)


class SettingsPatch(BaseModel):
    asr: Optional[AsrSettings] = None
    diar: Optional[DiarSettings] = None
    llm: Optional[LlmSettings] = None
    prompts: Optional[dict[str, PromptSettings]] = None
    report: Optional[ReportSettings] = None
    advanced: Optional[AdvancedSettings] = None


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
