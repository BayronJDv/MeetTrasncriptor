# Taste
- Communicates in Spanish (task requests written in Spanish); respond in Spanish. Confidence: 0.6
- Wants every aspect of the tools built for them to be configurable by the user, not hardcoded (e.g. report template, AI provider, Whisper model size). Confidence: 0.85
- Wants long-running processes to show their status/progress in the UI, not just run silently (explicitly required for a ~3h transcription job). Confidence: 0.8
- Prefers local processing and free AI providers over paid/cloud-only options when building tools (explicitly requested 100% local audio processing and a "proveedor gratuito de IA"). Confidence: 0.8
- Wants solutions sized to this machine's actual hardware — it has a weak GPU (MX150, 2GB VRAM) and 16GB RAM; detect/ask for specs and default to CPU-friendly configs. Confidence: 0.75
- On this Windows machine, edit JSON config/data files with Python (`encoding='utf-8'`), never PowerShell 5.1 `Set-Content` — it prepends a BOM that breaks `json.loads`, silently falls back to defaults and wiped the user's stored API keys once. Confidence: 0.8
