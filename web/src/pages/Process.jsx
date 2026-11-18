import React, { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api, fmtDuration } from '../api.js'
import { ErrorNote, ProgressBar, btnPrimary, btnSecondary, useJob } from '../components.jsx'

export default function ProcessPage() {
  const { projectId } = useParams()
  const job = useJob()
  const [meta, setMeta] = useState(null)
  const [config, setConfig] = useState(null)
  const [engines, setEngines] = useState([])
  const [error, setError] = useState(null)

  const refresh = async () => {
    try {
      setMeta(await api.get(`/projects/${projectId}`))
      const [settings, catalog] = await Promise.all([api.get('/settings'), api.get('/catalog')])
      setConfig(settings.config)
      setEngines(catalog)
    } catch (e) {
      setError(e.message)
    }
  }

  useEffect(() => { refresh() }, [projectId])

  const running = job && ['queued', 'running'].includes(job.status)

  const start = async () => {
    setError(null)
    try {
      await api.post(`/projects/${projectId}/transcribe`)
    } catch (e) {
      setError(e.message)
    }
  }

  const cancel = async () => {
    try {
      await api.post(`/jobs/${job.id}/cancel`)
    } catch (e) {
      setError(e.message)
    }
  }

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">{meta?.name || '…'}</h1>
      <ErrorNote error={error} />

      <div className="rounded-xl border border-slate-200 bg-white p-5">
        <h2 className="mb-3 font-semibold">Estado del proceso</h2>

        {running ? (
          <div>
            <div className="mb-1 flex items-baseline justify-between">
              <span className="font-medium text-blue-800">{job.stage || 'En cola…'}</span>
              <span className="text-sm tabular-nums text-slate-600">{Math.round(job.progress)}%</span>
            </div>
            <ProgressBar value={job.progress} />
            {job.detail && <p className="mt-2 text-sm text-slate-600">{job.detail}</p>}
            {job.log?.length > 0 && (
              <pre className="mt-3 max-h-48 overflow-auto rounded bg-slate-900 p-3 text-xs leading-5 text-slate-200">
                {job.log.join('\n')}
              </pre>
            )}
            <button onClick={cancel} className={`${btnSecondary} mt-3`}>
              Cancelar proceso
            </button>
          </div>
        ) : (
          <div>
            {meta?.has_transcript ? (
              <p className="mb-3 text-sm text-slate-600">
                Transcripción lista ({fmtDuration(meta.duration)}). Continúa a la etapa de{' '}
                <Link className="text-blue-600 hover:underline" to={`/p/${projectId}/hablantes`}>
                  identificación de hablantes
                </Link>
                .
              </p>
            ) : (
              <p className="mb-3 text-sm text-slate-600">
                Inicia la transcripción con identificación de voces. En tu equipo (CPU int8 + diarización)
                un audio de 3 h puede tardar alrededor de 1–2 h; puedes dejarlo trabajando y volver después.
              </p>
            )}
            <button onClick={start} disabled={!meta || running} className={btnPrimary}>
              {meta?.has_transcript ? 'Volver a transcribir' : 'Iniciar transcripción'}
            </button>
            {job?.status === 'error' && (
              <p className="mt-3 rounded bg-red-50 p-3 text-sm text-red-700">Error: {job.error}</p>
            )}
            {job?.status === 'cancelled' && (
              <p className="mt-3 text-sm text-amber-700">Proceso cancelado. Puedes reiniciarlo.</p>
            )}
          </div>
        )}
      </div>

      {config && (
        <div className="rounded-xl border border-slate-200 bg-white p-5">
          <h2 className="mb-2 font-semibold">Configuración activa</h2>
          <ul className="grid gap-1 text-sm text-slate-600 sm:grid-cols-2">
            <li>ASR: <b>{engines.find((engine) => engine.id === config.asr.engine)?.label || config.asr.engine}</b> · modelo <b>{config.asr.options?.[config.asr.engine]?.model || (config.asr.engine === 'whisperx' ? config.asr.model : 'No configurado')}</b></li>
            <li>Idioma: <b>{config.asr.language || config.asr.options?.[config.asr.engine]?.language || 'automático'}</b></li>
            <li>Diarización: <b>{engines.find((engine) => engine.id === config.diar.engine)?.label || config.diar.engine}</b> · modelo <b>{config.diar.options?.[config.diar.engine]?.model || (config.diar.engine === 'pyannote' ? 'pyannote/speaker-diarization-3.1' : 'No configurado')}</b></li>
            <li>Tramos: <b>{config.asr.options?.[config.asr.engine]?.chunk_minutes || config.asr.chunk_minutes} min</b></li>
          </ul>
          <Link to="/ajustes" className="mt-3 inline-block text-sm text-blue-600 hover:underline">
            Cambiar en Ajustes →
          </Link>
        </div>
      )}
    </div>
  )
}
