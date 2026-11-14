import React, { useCallback, useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, fmtDuration, uploadWithProgress } from '../api.js'
import { ErrorNote, ProgressBar, StageBadge, btnPrimary, inputCls } from '../components.jsx'

export default function ProjectsPage() {
  const [projects, setProjects] = useState([])
  const [error, setError] = useState(null)
  const [uploadPct, setUploadPct] = useState(null)
  const [dragOver, setDragOver] = useState(false)
  const fileRef = useRef(null)

  const refresh = useCallback(async () => {
    try {
      setProjects(await api.get('/projects'))
      setError(null)
    } catch (e) {
      setError(e.message)
    }
  }, [])

  useEffect(() => {
    refresh()
    const t = setInterval(refresh, 4000)
    return () => clearInterval(t)
  }, [refresh])

  const upload = async (file) => {
    if (!file) return
    setError(null)
    setUploadPct(0)
    try {
      const fd = new FormData()
      fd.append('file', file)
      await uploadWithProgress('/projects', fd, setUploadPct)
      await refresh()
    } catch (e) {
      setError(e.message)
    } finally {
      setUploadPct(null)
      if (fileRef.current) fileRef.current.value = ''
    }
  }

  const remove = async (p) => {
    if (!confirm(`¿Eliminar el proyecto "${p.name}" y todos sus archivos?`)) return
    try {
      await api.del(`/projects/${p.id}`)
      refresh()
    } catch (e) {
      setError(e.message)
    }
  }

  return (
    <div>
      <h1 className="mb-4 text-2xl font-bold">Proyectos</h1>
      <ErrorNote error={error} />

      <div
        onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e) => { e.preventDefault(); setDragOver(false); upload(e.dataTransfer.files[0]) }}
        onClick={() => fileRef.current?.click()}
        className={`mb-6 cursor-pointer rounded-xl border-2 border-dashed p-8 text-center transition ${
          dragOver ? 'border-blue-500 bg-blue-50' : 'border-slate-300 bg-white hover:border-blue-400'
        }`}
      >
        <p className="text-lg font-medium">Arrastra un audio aquí o haz clic para elegirlo</p>
        <p className="mt-1 text-sm text-slate-500">
          WAV, MP3, M4A, OGG, FLAC… también videos (MP4). Audios largos de varias horas OK.
        </p>
        <input
          ref={fileRef}
          type="file"
          accept="audio/*,video/*"
          className="hidden"
          onChange={(e) => upload(e.target.files[0])}
        />
      </div>

      {uploadPct != null && (
        <div className="mb-6 rounded-lg border border-blue-200 bg-blue-50 p-4">
          <p className="mb-2 text-sm font-medium text-blue-900">Subiendo archivo… {uploadPct}%</p>
          <ProgressBar value={uploadPct} />
        </div>
      )}

      <div className="space-y-2">
        {projects.map((p) => (
          <div key={p.id} className="flex items-center justify-between rounded-lg border border-slate-200 bg-white p-4">
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <Link to={`/p/${p.id}/proceso`} className="truncate font-semibold hover:text-blue-700">
                  {p.name}
                </Link>
                <StageBadge stage={p.stage} />
              </div>
              <p className="mt-0.5 text-xs text-slate-500">
                {fmtDuration(p.duration)} · {(p.size / 1024 / 1024).toFixed(1)} MB · {p.created_at}
              </p>
            </div>
            <div className="flex shrink-0 items-center gap-2">
              <Link to={`/p/${p.id}/hablantes`} className="text-sm text-blue-600 hover:underline">
                Abrir
              </Link>
              <button onClick={() => remove(p)} className="text-sm text-red-500 hover:underline">
                Eliminar
              </button>
            </div>
          </div>
        ))}
        {projects.length === 0 && (
          <p className="rounded-lg bg-white p-6 text-center text-sm text-slate-500">
            Aún no hay proyectos. Sube tu primer audio para empezar.
          </p>
        )}
      </div>
    </div>
  )
}
