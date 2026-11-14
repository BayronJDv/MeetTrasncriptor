import React, { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { api, fmtTime } from '../api.js'
import {
  AudioPlayer, ErrorNote, ProgressBar, btnPrimary, btnSecondary, useJob,
} from '../components.jsx'

const STATUS_LABELS = { pending: 'Pendiente', accepted: 'Aceptada', edited: 'Editada', rejected: 'Rechazada' }
const STATUS_COLORS = {
  pending: 'bg-blue-100 text-blue-700',
  accepted: 'bg-green-100 text-green-700',
  edited: 'bg-amber-100 text-amber-700',
  rejected: 'bg-slate-100 text-slate-500',
}

export default function ReviewPage() {
  const { projectId } = useParams()
  const job = useJob()
  const [state, setState] = useState(null)
  const [error, setError] = useState(null)
  const [filter, setFilter] = useState('pending')
  const [seek, setSeek] = useState({ start: null, end: null, key: 0 })

  const load = async () => {
    try {
      setState(await api.get(`/projects/${projectId}/review`))
      setError(null)
    } catch (e) {
      setError(e.message)
    }
  }

  useEffect(() => {
    load()
    const t = setInterval(load, 5000)
    return () => clearInterval(t)
  }, [projectId])

  const running = job && job.kind === 'review' && ['queued', 'running'].includes(job.status)

  const start = async () => {
    setError(null)
    try {
      await api.post(`/projects/${projectId}/review/start`)
    } catch (e) {
      setError(e.message)
    }
  }

  const act = async (sug, status, replacement) => {
    try {
      await api.patch(`/projects/${projectId}/review/suggestions/${sug.id}`, { status, replacement })
      await load()
    } catch (e) {
      setError(e.message)
    }
  }

  const suggestions = (state?.suggestions || []).filter((s) => filter === 'all' || s.status === filter)
  const counts = { all: state?.suggestions?.length || 0 }
  for (const s of state?.suggestions || []) counts[s.status] = (counts[s.status] || 0) + 1

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-bold">Revisión asistida por IA</h1>
        <button onClick={start} disabled={running} className={btnPrimary}>
          {running ? 'Analizando…' : state?.suggestions?.length ? 'Volver a analizar' : 'Analizar transcripción'}
        </button>
      </div>
      <p className="text-sm text-slate-600">
        La IA busca fragmentos con errores evidentes de transcripción (palabras sin sentido, frases
        incoherentes). Escucha cada fragmento antes de aceptar el cambio.
      </p>
      <ErrorNote error={error} />

      {running && job && (
        <div className="rounded-lg border border-blue-200 bg-blue-50 p-4">
          <div className="mb-1 flex justify-between text-sm text-blue-900">
            <span className="font-medium">{job.stage}</span>
            <span className="tabular-nums">{Math.round(job.progress)}%</span>
          </div>
          <ProgressBar value={job.progress} />
          {job.detail && <p className="mt-1 text-xs text-blue-700">{job.detail}</p>}
        </div>
      )}

      <div className="flex flex-wrap gap-1">
        {['pending', 'accepted', 'edited', 'rejected', 'all'].map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`rounded-full px-3 py-1 text-xs font-medium ${
              filter === f ? 'bg-slate-800 text-white' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
            }`}
          >
            {f === 'all' ? 'Todas' : STATUS_LABELS[f]} {counts[f] ? `(${counts[f]})` : ''}
          </button>
        ))}
      </div>

      <div className="space-y-3">
        {suggestions.map((sug) => (
          <SuggestionCard key={sug.id} projectId={projectId} sug={sug} onPlay={(a, b) => setSeek((x) => ({ start: a, end: b, key: x.key + 1 }))} onAct={act} />
        ))}
        {state && suggestions.length === 0 && state.status === 'done' && (
          <p className="rounded-lg bg-white p-4 text-sm text-slate-500">
            No hay sugerencias en este filtro. {filter === 'pending' && '¡Todo revisado!'}
          </p>
        )}
      </div>

      <div className="sticky bottom-0 border-t border-slate-200 bg-white/95 p-3 backdrop-blur">
        <AudioPlayer
          src={`/api/projects/${projectId}/audio`}
          start={seek.start}
          end={seek.end}
          seekKey={seek.key}
        />
      </div>
    </div>
  )
}

function SuggestionCard({ projectId, sug, onPlay, onAct }) {
  const [editing, setEditing] = useState(false)
  const [replacement, setReplacement] = useState(sug.suggestion)

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4">
      <div className="mb-2 flex flex-wrap items-center gap-2 text-xs">
        <span className={`rounded-full px-2 py-0.5 font-medium ${STATUS_COLORS[sug.status]}`}>
          {STATUS_LABELS[sug.status]}
        </span>
        <button onClick={() => onPlay(sug.start, sug.end)} className="text-blue-600 hover:underline">
          ▶ Escuchar {fmtTime(sug.start)}
        </button>
        <span className="text-slate-400">segmentos {sug.ids.join(', ')}</span>
      </div>
      <div className="grid gap-2 md:grid-cols-2">
        <div className="rounded-lg bg-red-50 p-3 text-sm">
          <p className="mb-1 text-xs font-semibold text-red-500">Texto actual</p>
          <p className="text-red-900">“{sug.original}”</p>
        </div>
        <div className="rounded-lg bg-green-50 p-3 text-sm">
          <p className="mb-1 text-xs font-semibold text-green-600">Sugerencia de la IA</p>
          {editing ? (
            <textarea
              value={replacement}
              onChange={(e) => setReplacement(e.target.value)}
              rows={2}
              className="w-full rounded border border-green-300 p-2 text-sm outline-none"
            />
          ) : (
            <p className="text-green-900">“{sug.suggestion}”</p>
          )}
        </div>
      </div>
      {sug.reason && <p className="mt-2 text-xs italic text-slate-500">Motivo: {sug.reason}</p>}
      <div className="mt-3 flex flex-wrap gap-2">
        {sug.status === 'pending' && (
          <>
            <button onClick={() => onAct(sug, 'accepted')} className="rounded-md bg-green-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-green-700">
              ✓ Aceptar
            </button>
            {editing ? (
              <button onClick={() => { onAct(sug, 'edited', replacement); setEditing(false) }} className={btnSecondary}>
                Guardar edición
              </button>
            ) : (
              <button onClick={() => { setReplacement(sug.suggestion); setEditing(true) }} className={btnSecondary}>
                Editar y aplicar
              </button>
            )}
            <button onClick={() => onAct(sug, 'rejected')} className={btnSecondary}>
              ✕ Rechazar
            </button>
          </>
        )}
      </div>
    </div>
  )
}
