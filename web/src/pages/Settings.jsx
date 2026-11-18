import React, { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api.js'
import { ErrorNote, Field, btnPrimary, btnSecondary, inputCls } from '../components.jsx'
import PromptEditor from '../components/settings/PromptEditor.jsx'
import EnginePanel from '../components/settings/EnginePanel.jsx'

const MODELS = ['tiny', 'base', 'small', 'medium', 'large-v2', 'large-v3']
const LANGS = ['es', 'en', 'pt', 'fr', 'de', 'it', '']

export default function SettingsPage() {
  const [data, setData] = useState(null)
  const [system, setSystem] = useState(null)
  const [cfg, setCfg] = useState(null)
  const [error, setError] = useState(null)
  const [saved, setSaved] = useState(false)
  const [llmModels, setLlmModels] = useState([])
  const [connectionResult, setConnectionResult] = useState(null)
  const [testingConnection, setTestingConnection] = useState(false)
  const [selectedTask, setSelectedTask] = useState('review')

  const loadLlmModels = async (provider) => {
    try {
      const result = await api.get(`/llm/models?provider=${encodeURIComponent(provider)}`)
      setLlmModels(result.models || [])
    } catch {
      setLlmModels([])
    }
  }

  useEffect(() => {
    Promise.all([api.get('/settings'), api.get('/system'), api.get('/prompts')])
      .then(([s, sys, prompts]) => {
        setData(s)
        setCfg({ ...s.config, prompts })
        setSystem(sys)
        loadLlmModels(s.config.llm.provider)
      })
      .catch((e) => setError(e.message))
  }, [])

  const patch = (section, key, value) => {
    setCfg((c) => ({ ...c, [section]: { ...c[section], [key]: value } }))
    setSaved(false)
  }

  const save = async () => {
    setError(null)
    try {
      const res = await api.put('/settings', cfg)
      setCfg(res.config)
      setSaved(true)
    } catch (e) {
      setError(e.message)
    }
  }

  const testConnection = async () => {
    setTestingConnection(true)
    setConnectionResult(null)
    try {
      const result = await api.post('/llm/test', {
        provider: cfg.llm.provider,
        model: cfg.llm.model,
        base_url: cfg.llm.base_url || undefined,
      })
      setConnectionResult(result)
    } catch (e) {
      setConnectionResult({ ok: false, error: e.message })
    } finally {
      setTestingConnection(false)
    }
  }

  const patchTaskModel = (task, model) => {
    setCfg((c) => ({
      ...c,
      llm: { ...c.llm, tasks: { ...c.llm.tasks, [task]: { ...c.llm.tasks?.[task], model } } },
    }))
    setSaved(false)
  }

  const patchPrompts = (prompts) => {
    setCfg((c) => ({ ...c, prompts }))
    setSaved(false)
  }

  if (!cfg) return <p className="p-6 text-sm text-slate-500">Cargando ajustes…</p>

  const providerModels = data?.providers?.[cfg.llm.provider]?.models || []

  return (
    <div className="mx-auto max-w-3xl space-y-4 p-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Ajustes</h1>
        <Link to="/" className={btnSecondary}>← Volver</Link>
      </div>
      <ErrorNote error={error} />
      {saved && <p className="rounded-md bg-green-50 px-3 py-2 text-sm text-green-700">Ajustes guardados ✓</p>}

      {system && (
        <div className="rounded-xl border border-slate-200 bg-white p-4 text-sm">
          <div className="mb-2 flex items-center justify-between">
            <h2 className="font-semibold">Este equipo</h2>
          </div>
          <ul className="grid gap-1 text-slate-600 sm:grid-cols-2">
            <li>CPU: {system.cpu || '—'}</li>
            <li>RAM: {system.ram_gb ? `${system.ram_gb} GB` : '—'}</li>
            <li>GPU: {system.cuda_available ? `${system.gpu} (${system.gpu_vram_gb} GB)` : 'sin CUDA activo'}</li>
            <li>PyTorch: {system.torch}</li>
          </ul>
          <p className="mt-2 text-xs text-slate-500">{system.recommendation?.note}</p>
        </div>
      )}

      <EnginePanel cfg={cfg} onChange={patch} system={system} />

      {/* ---- WhisperX ---- */}
      <section className="rounded-xl border border-slate-200 bg-white p-4">
        <h2 className="mb-3 font-semibold">Transcripción (WhisperX)</h2>
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="Tamaño del modelo" hint="small: rápido (recomendado en este PC) · medium/large: mejor calidad, mucho más lento">
            <select value={cfg.asr.model} onChange={(e) => patch('asr', 'model', e.target.value)} className={inputCls}>
              {MODELS.map((m) => <option key={m} value={m}>{m}</option>)}
            </select>
          </Field>
          <Field label="Idioma" hint="Vacío = detección automática (más lento)">
            <select value={cfg.asr.language} onChange={(e) => patch('asr', 'language', e.target.value)} className={inputCls}>
              {LANGS.map((l) => <option key={l} value={l}>{l || 'automático'}</option>)}
            </select>
          </Field>
          <Field label="Dispositivo ASR">
            <select value={cfg.asr.device} onChange={(e) => patch('asr', 'device', e.target.value)} className={inputCls}>
              <option value="cpu">CPU</option>
              <option value="cuda">GPU (CUDA)</option>
            </select>
          </Field>
          <Field label="Tipo de cálculo" hint="int8: ideal en CPU con poca VRAM">
            <select value={cfg.asr.compute_type} onChange={(e) => patch('asr', 'compute_type', e.target.value)} className={inputCls}>
              <option value="int8">int8</option>
              <option value="float16">float16</option>
              <option value="float32">float32</option>
            </select>
          </Field>
          <Field label="Batch size">
            <input type="number" min={1} max={64} value={cfg.asr.batch_size} onChange={(e) => patch('asr', 'batch_size', +e.target.value)} className={inputCls} />
          </Field>
          <Field label="Duración de tramos (min)" hint="Tramos más cortos = progreso más fino">
            <input type="number" min={1} max={30} value={cfg.asr.chunk_minutes} onChange={(e) => patch('asr', 'chunk_minutes', +e.target.value)} className={inputCls} />
          </Field>
        </div>
      </section>

      {/* ---- Diarización ---- */}
      <section className="rounded-xl border border-slate-200 bg-white p-4">
        <h2 className="mb-1 font-semibold">Diarización (pyannote)</h2>
        <p className="mb-3 text-xs text-slate-500">
          Requiere un token de HuggingFace (gratis) tras aceptar los términos de
          pyannote/segmentation-3.0 y pyannote/speaker-diarization-3.1 en hf.co.
        </p>
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="Token de HuggingFace">
            <input type="password" value={cfg.diar.hf_token} onChange={(e) => patch('diar', 'hf_token', e.target.value)} placeholder="hf_..." className={inputCls} />
          </Field>
          <Field label="Dispositivo de diarización" hint="GPU acelera mucho la diarización si hay torch-CUDA">
            <select value={cfg.diar.device} onChange={(e) => patch('diar', 'device', e.target.value)} className={inputCls}>
              <option value="auto">Automático</option>
              <option value="cpu">CPU</option>
              <option value="cuda">GPU (CUDA)</option>
            </select>
          </Field>
          <Field label="Nº de hablantes (mín)" hint="Vacío = automático">
            <input type="number" min={1} max={20} value={cfg.diar.min_speakers ?? ''} onChange={(e) => patch('diar', 'min_speakers', e.target.value === '' ? null : +e.target.value)} className={inputCls} />
          </Field>
          <Field label="Nº de hablantes (máx)" hint="Vacío = automático">
            <input type="number" min={1} max={20} value={cfg.diar.max_speakers ?? ''} onChange={(e) => patch('diar', 'max_speakers', e.target.value === '' ? null : +e.target.value)} className={inputCls} />
          </Field>
          <Field label="Clips por hablante">
            <input type="number" min={1} max={10} value={cfg.diar.clips_per_speaker} onChange={(e) => patch('diar', 'clips_per_speaker', +e.target.value)} className={inputCls} />
          </Field>
        </div>
      </section>

      {/* ---- IA ---- */}
      <section className="rounded-xl border border-slate-200 bg-white p-4">
        <h2 className="mb-3 font-semibold">Inteligencia artificial (revisión e informe)</h2>
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="Proveedor" hint="Todos usan el formato OpenAI; Ollama es 100% local">
            <select
              value={cfg.llm.provider}
              onChange={(e) => {
                const p = e.target.value
                const models = data?.providers?.[p]?.models || []
                setCfg((c) => ({ ...c, llm: { ...c.llm, provider: p, model: models[0] || c.llm.model, base_url: '' } }))
                setSaved(false)
                setConnectionResult(null)
                loadLlmModels(p)
              }}
              className={inputCls}
            >
              {Object.keys(data?.providers || {}).map((p) => <option key={p} value={p}>{p}</option>)}
            </select>
          </Field>
          <Field label="Modelo" hint="Escribe uno propio si el proveedor ofrece otros">
            <input list="model-suggestions" value={cfg.llm.model} onChange={(e) => patch('llm', 'model', e.target.value)} className={inputCls} />
            <datalist id="model-suggestions">
              {[...new Set([...providerModels, ...llmModels])].map((m) => <option key={m} value={m} />)}
            </datalist>
          </Field>
          <Field label="Tarea LLM">
            <select value={selectedTask} onChange={(e) => setSelectedTask(e.target.value)} className={inputCls}>
              {Object.keys(cfg.llm.tasks || {}).map((task) => <option key={task} value={task}>{task}</option>)}
            </select>
          </Field>
          <Field label={`Modelo para ${selectedTask}`} hint="Vacío = usar el modelo general">
            <input
              list="task-model-suggestions"
              value={cfg.llm.tasks?.[selectedTask]?.model || ''}
              placeholder={cfg.llm.model}
              onChange={(e) => patchTaskModel(selectedTask, e.target.value || null)}
              className={inputCls}
            />
            <datalist id="task-model-suggestions">
              {[...new Set([...providerModels, ...llmModels])].map((m) => <option key={m} value={m} />)}
            </datalist>
          </Field>
          <div className="flex items-end">
            <button type="button" onClick={testConnection} disabled={testingConnection} className={btnSecondary}>
              {testingConnection ? 'Probando…' : 'Probar conexión'}
            </button>
          </div>
          {connectionResult && (
            <p className={`sm:col-span-2 text-sm ${connectionResult.ok ? 'text-green-700' : 'text-red-700'}`}>
              {connectionResult.ok ? 'Conexión correcta.' : connectionResult.error || 'No se pudo conectar.'}
              {!connectionResult.ok && cfg.llm.provider === 'ollama' && (
                <> Asegúrate de que Ollama está iniciado y ejecuta <code>ollama pull {cfg.llm.model}</code>.</>
              )}
            </p>
          )}
          {!llmModels.length && cfg.llm.provider === 'ollama' && (
            <p className="sm:col-span-2 text-sm text-amber-700">
              No se pudo conectar con Ollama o no hay modelos disponibles. Inicia Ollama y ejecuta <code>ollama pull {cfg.llm.model}</code>.
            </p>
          )}
          <Field label="API key" hint={data?.providers?.[cfg.llm.provider]?.needs_key ? 'Requerida para este proveedor (gratis en su web)' : 'No requerida'}>
            <input type="password" value={cfg.llm.api_key} onChange={(e) => patch('llm', 'api_key', e.target.value)} className={inputCls} />
          </Field>
          <Field label="URL base (opcional)" hint="Solo para proveedor personalizado o Ollama remoto">
            <input value={cfg.llm.base_url} onChange={(e) => patch('llm', 'base_url', e.target.value)} placeholder={data?.providers?.[cfg.llm.provider]?.base_url} className={inputCls} />
          </Field>
          <Field label="Ventana de análisis (min)">
            <input type="number" min={2} max={60} value={cfg.llm.window_minutes} onChange={(e) => patch('llm', 'window_minutes', +e.target.value)} className={inputCls} />
          </Field>
          <Field label="Peticiones simultáneas" hint="Bajo (2) para no agotar los límites gratuitos">
            <input type="number" min={1} max={8} value={cfg.llm.concurrency} onChange={(e) => patch('llm', 'concurrency', +e.target.value)} className={inputCls} />
          </Field>
          <Field label="Temperatura">
            <input type="number" step="0.1" min={0} max={2} value={cfg.llm.temperature} onChange={(e) => patch('llm', 'temperature', +e.target.value)} className={inputCls} />
          </Field>
          <Field label="Reintentos ante límite">
            <input type="number" min={0} max={10} value={cfg.llm.max_retries} onChange={(e) => patch('llm', 'max_retries', +e.target.value)} className={inputCls} />
          </Field>
        </div>
      </section>

      <PromptEditor prompts={cfg.prompts || {}} onChange={patchPrompts} />

      <div className="flex justify-end">
        <button onClick={save} className={btnPrimary}>Guardar ajustes</button>
      </div>
    </div>
  )
}
