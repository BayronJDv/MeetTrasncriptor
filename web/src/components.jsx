import React, { createContext, useContext, useEffect, useRef, useState } from 'react'

// ---------- contexto de progreso del proyecto (SSE) ----------

const JobContext = createContext(null)

export function JobProvider({ projectId, children }) {
  const [job, setJob] = useState(null)
  const esRef = useRef(null)

  useEffect(() => {
    if (!projectId) return
    const es = new EventSource(`/api/projects/${projectId}/events`)
    esRef.current = es
    es.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data)
        if (data.type === 'job') setJob(data.job)
      } catch { /* evento inválido */ }
    }
    es.onerror = () => { /* EventSource reconecta solo */ }
    return () => es.close()
  }, [projectId])

  return <JobContext.Provider value={job}>{children}</JobContext.Provider>
}

export function useJob() {
  return useContext(JobContext)
}

// ---------- barra de progreso ----------

export function ProgressBar({ value, className = '' }) {
  const v = Math.max(0, Math.min(100, value ?? 0))
  return (
    <div className={`h-2 w-full overflow-hidden rounded-full bg-slate-200 ${className}`}>
      <div
        className="h-full rounded-full bg-blue-600 transition-all duration-500"
        style={{ width: `${v}%` }}
      />
    </div>
  )
}

// ---------- insignias de estado ----------

const STAGE_LABELS = {
  created: 'Sin transcribir',
  transcribing: 'Transcribiendo',
  speakers: 'Hablantes',
  review: 'Revisión IA',
  meeting: 'Estructura',
  report: 'Informe',
  done: 'Completo',
}

export function StageBadge({ stage }) {
  const map = {
    created: 'bg-slate-100 text-slate-600',
    transcribing: 'bg-amber-100 text-amber-700',
    speakers: 'bg-violet-100 text-violet-700',
    review: 'bg-sky-100 text-sky-700',
    meeting: 'bg-teal-100 text-teal-700',
    report: 'bg-emerald-100 text-emerald-700',
    done: 'bg-green-100 text-green-700',
  }
  return (
    <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${map[stage] || map.created}`}>
      {STAGE_LABELS[stage] || stage}
    </span>
  )
}

export function JobBanner() {
  const job = useJob()
  if (!job || !['queued', 'running'].includes(job.status)) return null
  return (
    <div className="rounded-lg border border-blue-200 bg-blue-50 p-3 text-sm text-blue-900">
      <div className="mb-1 flex items-center justify-between gap-4">
        <span className="font-medium">
          {job.kind === 'transcribe' && 'Transcribiendo'}
          {job.kind === 'review' && 'Revisión IA en curso'}
          {job.kind === 'meeting' && 'Analizando estructura'}
          {job.kind === 'report' && 'Generando informe'}
          {job.stage ? ` · ${job.stage}` : ''}
        </span>
        <span className="tabular-nums">{Math.round(job.progress)}%</span>
      </div>
      <ProgressBar value={job.progress} />
      {job.detail && <p className="mt-1 text-xs text-blue-700">{job.detail}</p>}
    </div>
  )
}

// ---------- reproductor de audio con seek ----------

export function AudioPlayer({ src, start, end, seekKey, className = '' }) {
  const ref = useRef(null)

  useEffect(() => {
    const audio = ref.current
    if (!audio || start == null || !seekKey) return
    audio.currentTime = Math.max(0, start - 0.3)
    audio.play().catch(() => { /* autoplay bloqueado */ })
  }, [seekKey])

  const onTimeUpdate = () => {
    const audio = ref.current
    if (audio && end != null && audio.currentTime >= end) audio.pause()
  }

  return (
    <audio
      ref={ref}
      src={src}
      controls
      preload="none"
      onTimeUpdate={onTimeUpdate}
      className={`w-full ${className}`}
    />
  )
}

// ---------- campos de formulario ----------

export function Field({ label, children, hint }) {
  return (
    <label className="block text-sm">
      <span className="mb-1 block font-medium text-slate-700">{label}</span>
      {children}
      {hint && <span className="mt-1 block text-xs text-slate-500">{hint}</span>}
    </label>
  )
}

export const inputCls =
  'w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100'

export const btnPrimary =
  'rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50'

export const btnSecondary =
  'rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50'

export function ErrorNote({ error }) {
  if (!error) return null
  return <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{String(error)}</p>
}
