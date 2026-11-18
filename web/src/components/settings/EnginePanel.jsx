import React, { useEffect, useState } from 'react'
import { api } from '../../api.js'
import { ErrorNote, Field, ProgressBar, btnPrimary, inputCls } from '../../components.jsx'

const requirementLabel = ({ type, value }) => ({
  hf_token: 'Token de Hugging Face configurado',
  hf_terms: 'Aceptar términos del modelo',
  ram_gb: `${value} GB de RAM`,
  vram_gb: `${value} GB de VRAM recomendados`,
  pip_extra: `Dependencia opcional: ${value}`,
  binary: `Binario: ${value}`,
}[type] || `${type}: ${value}`)

const requirementMet = (engine, requirement, cfg, system) => {
  if (requirement.type === 'hf_token') return Boolean(cfg.diar.hf_token || cfg.diar.options?.pyannote?.hf_token)
  if (requirement.type === 'hf_terms' || requirement.type === 'pip_extra') return engine.installed
  if (requirement.type === 'ram_gb') return system?.ram_gb >= requirement.value
  if (requirement.type === 'vram_gb') return system?.vram_gb >= requirement.value
  if (requirement.type === 'binary') return Boolean(system?.capabilities?.nemo_speech)
  return false
}

export default function EnginePanel({ cfg, onChange, system }) {
  const [catalog, setCatalog] = useState([])
  const [error, setError] = useState(null)
  const [job, setJob] = useState(null)
  const [termsAccepted, setTermsAccepted] = useState(false)

  const loadCatalog = async () => {
    try {
      setCatalog(await api.get('/catalog'))
    } catch (e) {
      setError(e.message)
    }
  }

  useEffect(() => { loadCatalog() }, [])

  useEffect(() => {
    if (!job || !['queued', 'running'].includes(job.status)) return
    let active = true
    const refreshJob = async () => {
      try {
        const latest = await api.get('/projects/__system__/job')
        if (!active || latest.id !== job.id) return
        setJob(latest)
        if (latest.status === 'done') loadCatalog()
      } catch (e) {
        if (active) setError(e.message)
      }
    }
    refreshJob()
    const interval = setInterval(refreshJob, 500)
    return () => {
      active = false
      clearInterval(interval)
    }
  }, [job?.id, job?.status])

  const engines = (kind) => catalog.filter((engine) => engine.kind === kind)
  const selectedAsr = catalog.find((engine) => engine.id === cfg.asr.engine)
  const selectedDiar = catalog.find((engine) => engine.id === cfg.diar.engine)
  const recommendation = system?.recommendations?.find((item) => item.applies)
  const recommendationEngines = (recommendation?.engines?.length
    ? recommendation.engines
    : recommendation?.available_engines || (recommendation?.engine ? [recommendation.engine] : []))
    .map((id) => catalog.find((engine) => engine.id === id)?.label || id)

  const install = async (engine) => {
    setError(null)
    setJob(null)
    try {
      const payload = engine.id === 'pyannote' ? { terms_confirmation: 'Acepto los términos' } : undefined
      setJob(await api.post(`/engines/${engine.id}/install`, payload))
    } catch (e) {
      setError(e.message)
    }
  }

  const renderEngine = (engine) => (
    <div key={engine.id} className="space-y-2 rounded-lg border border-slate-200 p-3">
      <p className="font-medium">{engine.label} · {engine.installed ? 'Instalado' : 'No instalado'}</p>
      <ul className="space-y-1 text-xs text-slate-600">
        {engine.requirements.map((requirement, index) => (
          <li key={`${engine.id}-${index}`} className={requirementMet(engine, requirement, cfg, system) ? 'text-green-700' : 'text-amber-700'}>
            {requirement.type === 'hf_terms' ? (
              <a href={requirement.url} target="_blank" rel="noreferrer" className="hover:underline">
                {requirementLabel(requirement)} ↗
              </a>
            ) : <span>{requirementLabel(requirement)}{requirement.type === 'hf_token' ? (requirementMet(engine, requirement, cfg, system) ? ' · configurado' : ' · falta') : ''}</span>}
            {' · '}{requirement.type === 'hf_terms' && engine.id === 'pyannote' && termsAccepted ? 'cumplido' : requirementMet(engine, requirement, cfg, system) ? 'cumplido' : 'pendiente'}
          </li>
        ))}
      </ul>
      {engine.id === 'pyannote' && (
        <label className="flex items-center gap-2 text-sm text-slate-700">
          <input type="checkbox" checked={termsAccepted} onChange={(event) => setTermsAccepted(event.target.checked)} />
          Acepto los términos de pyannote
        </label>
      )}
      {engine.attribution && engine.license === 'CC-BY-4.0' && (
        <p className="text-xs text-slate-500">Atribución {engine.license}: {engine.attribution}</p>
      )}
      {engine.id === 'parakeet_gguf' || engine.id === 'nemotron_gguf' ? (
        <p className="text-xs text-slate-500">Instalación manual: {engine.install_hint}</p>
      ) : (
        <button
          type="button"
          disabled={engine.installed || (engine.id === 'pyannote' && !termsAccepted) || Boolean(job && ['queued', 'running'].includes(job.status))}
          onClick={() => install(engine)}
          className={btnPrimary}
        >
          {engine.installed ? 'Instalado' : 'Instalar'}
        </button>
      )}
    </div>
  )

  return (
    <section className="space-y-4 rounded-xl border border-slate-200 bg-white p-4">
      <div>
        <h2 className="font-semibold">Motores de transcripción</h2>
        {recommendation && (
          <p className="mt-2 rounded-md bg-blue-50 p-3 text-sm text-blue-900">
            Recomendación para este equipo: {recommendationEngines.join(' + ') || recommendation.profile}.
          </p>
        )}
      </div>
      <ErrorNote error={error} />
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="Motor ASR">
          <select value={cfg.asr.engine} onChange={(event) => onChange('asr', 'engine', event.target.value)} className={inputCls}>
            {engines('asr').map((engine) => <option key={engine.id} value={engine.id}>{engine.label}</option>)}
          </select>
        </Field>
        <Field label="Motor de diarización">
          <select value={cfg.diar.engine} onChange={(event) => onChange('diar', 'engine', event.target.value)} className={inputCls}>
            {engines('diarization').map((engine) => <option key={engine.id} value={engine.id}>{engine.label}</option>)}
          </select>
        </Field>
      </div>
      {catalog.length > 0 && (
        <div className="grid gap-3 sm:grid-cols-2">
          {selectedAsr && renderEngine(selectedAsr)}
          {selectedDiar && renderEngine(selectedDiar)}
        </div>
      )}
      {job && (
        <div className="space-y-2 rounded-md bg-slate-50 p-3 text-sm" role="status" aria-live="polite">
          <div className="flex justify-between gap-3">
            <span>{job.detail || job.stage || 'Instalación'}</span>
            <span>{Math.round(job.progress || 0)}%</span>
          </div>
          <ProgressBar value={job.progress} />
          {job.status === 'error' && <p className="text-red-700">Error de instalación: {job.error || 'No se pudo instalar el motor.'}</p>}
          {job.status === 'done' && <p className="text-green-700">Instalación completada.</p>}
          {job.status === 'cancelled' && <p className="text-amber-700">Instalación cancelada.</p>}
        </div>
      )}
    </section>
  )
}
