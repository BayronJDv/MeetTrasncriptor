import React, { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { api, fmtTime } from '../api.js'
import { ErrorNote, ProgressBar, btnPrimary, btnSecondary, inputCls, useJob } from '../components.jsx'

const TYPES = [
  ['tema', 'Tema'],
  ['decision', 'Decisión'],
  ['votacion', 'Votación'],
  ['compromiso', 'Compromiso'],
  ['conclusion', 'Conclusión'],
  ['otro', 'Otro'],
]

const TYPE_COLORS = {
  tema: 'bg-slate-100 text-slate-700',
  decision: 'bg-blue-100 text-blue-700',
  votacion: 'bg-purple-100 text-purple-700',
  compromiso: 'bg-amber-100 text-amber-700',
  conclusion: 'bg-green-100 text-green-700',
  otro: 'bg-slate-100 text-slate-500',
}

export default function MeetingPage() {
  const { projectId } = useParams()
  const job = useJob()
  const [state, setState] = useState(null)
  const [dirty, setDirty] = useState(false)
  const [error, setError] = useState(null)

  const load = async () => {
    try {
      const s = await api.get(`/projects/${projectId}/meeting`)
      setState(s)
    } catch (e) {
      setError(e.message)
    }
  }

  useEffect(() => { load() }, [projectId])

  const running = job && job.kind === 'meeting' && ['queued', 'running'].includes(job.status)

  const analyze = async () => {
    setError(null)
    try {
      await api.post(`/projects/${projectId}/meeting/analyze`)
    } catch (e) {
      setError(e.message)
    }
  }

  const save = async () => {
    try {
      const s = await api.put(`/projects/${projectId}/meeting`, { sections: state.sections })
      setState(s)
      setDirty(false)
    } catch (e) {
      setError(e.message)
    }
  }

  const patchSection = (idx, patch) => {
    setState((prev) => {
      const sections = prev.sections.map((s, i) => (i === idx ? { ...s, ...patch } : s))
      return { ...prev, sections }
    })
    setDirty(true)
  }

  const addSection = () => {
    setState((prev) => ({
      ...prev,
      sections: [...(prev?.sections || []), { id: `sec${Date.now()}`, type: 'tema', title: '', summary: '', items: [] }],
    }))
    setDirty(true)
  }

  const removeSection = (idx) => {
    setState((prev) => ({ ...prev, sections: prev.sections.filter((_, i) => i !== idx) }))
    setDirty(true)
  }

  const sections = state?.sections || []

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-bold">Estructura de la reunión</h1>
        <div className="flex gap-2">
          {dirty && (
            <button onClick={save} className="rounded-md bg-green-600 px-4 py-2 text-sm font-medium text-white hover:bg-green-700">
              Guardar cambios
            </button>
          )}
          <button onClick={analyze} disabled={running} className={btnPrimary}>
            {running ? 'Analizando…' : sections.length ? 'Re-analizar' : 'Analizar con IA'}
          </button>
        </div>
      </div>
      <p className="text-sm text-slate-600">
        La IA identifica temas, decisiones, votaciones, compromisos y conclusiones. Edita libremente el
        esquema antes de generar el informe.
      </p>
      <ErrorNote error={error} />

      {running && job && (
        <div className="rounded-lg border border-blue-200 bg-blue-50 p-4">
          <div className="mb-1 flex justify-between text-sm text-blue-900">
            <span className="font-medium">{job.stage}</span>
            <span className="tabular-nums">{Math.round(job.progress)}%</span>
          </div>
          <ProgressBar value={job.progress} />
        </div>
      )}

      {!running && !sections.length && state?.status !== 'done' && (
        <p className="rounded-lg bg-white p-4 text-sm text-slate-500">Aún no se ha analizado la reunión.</p>
      )}

      <div className="space-y-3">
        {sections.map((sec, idx) => (
          <div key={sec.id} className="rounded-xl border border-slate-200 bg-white p-4">
            <div className="mb-2 flex flex-wrap items-center gap-2">
              <select
                value={sec.type}
                onChange={(e) => patchSection(idx, { type: e.target.value })}
                className={`rounded-full px-2 py-1 text-xs font-semibold ${TYPE_COLORS[sec.type]}`}
              >
                {TYPES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
              </select>
              <input
                value={sec.title}
                onChange={(e) => patchSection(idx, { title: e.target.value })}
                placeholder="Título de la parte…"
                className={`${inputCls} flex-1`}
              />
              <span className="text-xs tabular-nums text-slate-400">
                {fmtTime(sec.start)} – {fmtTime(sec.end)}
              </span>
              <button onClick={() => removeSection(idx)} className="text-sm text-red-400 hover:text-red-600">✕</button>
            </div>
            <textarea
              value={sec.summary}
              onChange={(e) => patchSection(idx, { summary: e.target.value })}
              placeholder="Resumen…"
              rows={2}
              className={`${inputCls} mb-2`}
            />
            <textarea
              value={(sec.items || []).join('\n')}
              onChange={(e) => patchSection(idx, { items: e.target.value.split('\n').filter(Boolean) })}
              placeholder="Puntos concretos, votos, compromisos… (uno por línea)"
              rows={Math.max(2, (sec.items || []).length)}
              className={`${inputCls} text-sm`}
            />
          </div>
        ))}
      </div>

      {sections.length > 0 && (
        <button onClick={addSection} className={btnSecondary}>+ Añadir sección</button>
      )}
    </div>
  )
}
