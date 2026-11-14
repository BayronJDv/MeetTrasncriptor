import React, { useEffect, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import { useParams } from 'react-router-dom'
import { api, uploadWithProgress } from '../api.js'
import { ErrorNote, ProgressBar, btnPrimary, btnSecondary, inputCls, useJob } from '../components.jsx'

export default function ReportPage() {
  const { projectId } = useParams()
  const job = useJob()
  const [templates, setTemplates] = useState([])
  const [selected, setSelected] = useState(null)
  const [instructions, setInstructions] = useState('')
  const [includeMeeting, setIncludeMeeting] = useState(true)
  const [report, setReport] = useState(null)
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState('')
  const [error, setError] = useState(null)
  const [uploadPct, setUploadPct] = useState(null)

  const load = async () => {
    try {
      setTemplates(await api.get('/templates'))
      const meta = await api.get(`/projects/${projectId}`)
      setSelected(meta.report_template || null)
      try {
        const r = await api.get(`/projects/${projectId}/report`)
        setReport(r)
      } catch { /* sin informe aún */ }
    } catch (e) {
      setError(e.message)
    }
  }

  useEffect(() => { load() }, [projectId])

  const running = job && job.kind === 'report' && ['queued', 'running'].includes(job.status)

  const uploadTemplate = async (file) => {
    if (!file) return
    setError(null)
    setUploadPct(0)
    try {
      const fd = new FormData()
      fd.append('file', file)
      await uploadWithProgress('/templates', fd, setUploadPct)
      await load()
    } catch (e) {
      setError(e.message)
    } finally {
      setUploadPct(null)
    }
  }

  const removeTemplate = async (name) => {
    if (!confirm(`¿Eliminar la plantilla "${name}"?`)) return
    try {
      await api.del(`/templates?name=${encodeURIComponent(name)}`)
      if (selected === name) setSelected(null)
      load()
    } catch (e) {
      setError(e.message)
    }
  }

  const generate = async () => {
    setError(null)
    try {
      await api.post(`/projects/${projectId}/report/generate`, {
        template_name: selected,
        instructions,
        include_meeting: includeMeeting,
      })
    } catch (e) {
      setError(e.message)
    }
  }

  const saveEdit = async () => {
    try {
      await api.put(`/projects/${projectId}/report`, { markdown: draft })
      setReport({ markdown: draft })
      setEditing(false)
    } catch (e) {
      setError(e.message)
    }
  }

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">Generación del informe</h1>
      <ErrorNote error={error} />

      <div className="grid gap-4 lg:grid-cols-2">
        <div className="rounded-xl border border-slate-200 bg-white p-4">
          <h2 className="mb-2 font-semibold">Plantilla del informe</h2>
          <label className="mb-3 flex cursor-pointer items-center justify-center rounded-lg border-2 border-dashed border-slate-300 p-4 text-sm text-slate-500 hover:border-blue-400">
            <input
              type="file"
              accept=".md,.txt,.docx"
              className="hidden"
              onChange={(e) => uploadTemplate(e.target.files[0])}
            />
            {uploadPct != null ? `Subiendo… ${uploadPct}%` : 'Subir plantilla (.md, .txt o .docx)'}
          </label>
          {templates.length === 0 && (
            <p className="text-xs text-slate-400">
              Sin plantillas: también puedes escribir indicaciones libres más abajo.
            </p>
          )}
          <ul className="space-y-1">
            {templates.map((t) => (
              <li key={t.name} className="flex items-center justify-between rounded-md border border-slate-100 px-2 py-1.5 text-sm">
                <label className="flex flex-1 items-center gap-2 cursor-pointer">
                  <input
                    type="radio"
                    checked={selected === t.name}
                    onChange={() => setSelected(t.name)}
                  />
                  <span className="truncate">{t.name}</span>
                </label>
                <button onClick={() => removeTemplate(t.name)} className="text-xs text-red-400 hover:text-red-600">✕</button>
              </li>
            ))}
          </ul>
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-4">
          <h2 className="mb-2 font-semibold">Indicaciones para la IA</h2>
          <textarea
            value={instructions}
            onChange={(e) => setInstructions(e.target.value)}
            rows={6}
            placeholder="Ej.: 'Redacta un acta formal con: asistentes, orden del día, desarrollo, acuerdos y firmantes. Incluye el resultado de la votación del presupuesto.'"
            className={`${inputCls} mb-3`}
          />
          <label className="mb-3 flex items-center gap-2 text-sm">
            <input type="checkbox" checked={includeMeeting} onChange={(e) => setIncludeMeeting(e.target.checked)} />
            Usar la estructura de la reunión (etapa 4) como guía
          </label>
          <button onClick={generate} disabled={running} className={btnPrimary}>
            {running ? 'Generando informe…' : 'Generar informe'}
          </button>
        </div>
      </div>

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

      {report && (
        <div className="rounded-xl border border-slate-200 bg-white">
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 p-3">
            <h2 className="font-semibold">Informe</h2>
            <div className="flex gap-2">
              {editing ? (
                <>
                  <button onClick={saveEdit} className="rounded-md bg-green-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-green-700">
                    Guardar
                  </button>
                  <button onClick={() => { setEditing(false); setDraft('') }} className={btnSecondary}>Cancelar</button>
                </>
              ) : (
                <>
                  <button onClick={() => { setDraft(report.markdown); setEditing(true) }} className={btnSecondary}>Editar</button>
                  <a href={`/api/projects/${projectId}/report/export?format=docx`} className="rounded-md bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700">
                    Descargar .docx
                  </a>
                  <a href={`/api/projects/${projectId}/report/export?format=md`} className={btnSecondary}>
                    Descargar .md
                  </a>
                </>
              )}
            </div>
          </div>
          <div className="p-4">
            {editing ? (
              <textarea
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                rows={24}
                className={`${inputCls} font-mono text-xs`}
              />
            ) : (
              <div className="prose prose-sm max-w-none">
                <ReactMarkdown>{report.markdown}</ReactMarkdown>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
