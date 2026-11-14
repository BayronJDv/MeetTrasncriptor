import React, { useEffect, useMemo, useRef, useState } from 'react'
import { useParams } from 'react-router-dom'
import { api, fmtTime } from '../api.js'
import {
  AudioPlayer, ErrorNote, btnPrimary, btnSecondary, inputCls, useJob,
} from '../components.jsx'

const PAGE_SIZE = 150

export default function SpeakersPage() {
  const { projectId } = useParams()
  const job = useJob()
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [clipsBusy, setClipsBusy] = useState(false)
  const [seek, setSeek] = useState({ start: null, end: null, key: 0 })
  const [page, setPage] = useState(0)

  const load = async () => {
    try {
      setData(await api.get(`/projects/${projectId}/speakers`))
    } catch (e) {
      setError(e.message)
    }
  }

  useEffect(() => { load() }, [projectId])

  const play = (start, end) => setSeek((s) => ({ start, end, key: s.key + 1 }))

  const generateClips = async () => {
    setClipsBusy(true)
    setError(null)
    try {
      await api.post(`/projects/${projectId}/speakers/clips`)
      await load()
    } catch (e) {
      setError(e.message)
    } finally {
      setClipsBusy(false)
    }
  }

  const rename = async (speakerId, name) => {
    try {
      await api.post(`/projects/${projectId}/speakers/rename`, { speaker_id: speakerId, name })
      await load()
    } catch (e) {
      setError(e.message)
    }
  }

  const transcribing = job && job.kind === 'transcribe' && ['queued', 'running'].includes(job.status)

  if (!data && !error) return <p className="text-sm text-slate-500">Cargando…</p>

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-bold">Identificación de hablantes</h1>
        <button onClick={generateClips} disabled={clipsBusy || !data?.speakers?.length || transcribing} className={btnPrimary}>
          {clipsBusy ? 'Generando clips…' : 'Generar clips sugeridos'}
        </button>
      </div>
      <ErrorNote error={error} />

      {transcribing && (
        <p className="rounded-lg bg-amber-50 p-3 text-sm text-amber-800">
          Transcripción en curso: espera a que termine para editar los hablantes.
        </p>
      )}

      {data && data.speakers.length === 0 && (
        <p className="rounded-lg bg-white p-4 text-sm text-slate-600">
          No hay hablantes detectados. Si no configuraste el token de HuggingFace, la diarización se omitió
          (ver <a className="text-blue-600 hover:underline" href="/ajustes">Ajustes</a>).
        </p>
      )}

      {data && data.speakers.length > 0 && (
        <div className="grid gap-4 md:grid-cols-2">
          {data.speakers.map((sp) => (
            <SpeakerCard key={sp.id} projectId={projectId} speaker={sp} onRename={rename} onPlay={play} />
          ))}
        </div>
      )}

      {data && data.segments.length > 0 && (
        <TranscriptEditor
          projectId={projectId}
          segments={data.segments}
          speakers={data.speakers}
          page={page}
          setPage={setPage}
          onPlay={play}
          reload={load}
          onError={setError}
        />
      )}

      {/* reproductor compartido para fragmentos largos */}
      {data && (
        <div className="sticky bottom-0 border-t border-slate-200 bg-white/95 p-3 backdrop-blur">
          <AudioPlayer
            src={`/api/projects/${projectId}/audio`}
            start={seek.start}
            end={seek.end}
            seekKey={seek.key}
          />
        </div>
      )}
    </div>
  )
}

function SpeakerCard({ projectId, speaker, onRename, onPlay }) {
  const [name, setName] = useState(speaker.name || '')
  useEffect(() => setName(speaker.name || ''), [speaker.name])

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4">
      <div className="mb-3 flex items-center gap-2">
        <span className="rounded bg-violet-100 px-2 py-0.5 text-xs font-semibold text-violet-700">{speaker.id}</span>
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          onBlur={() => { if (name !== (speaker.name || '')) onRename(speaker.id, name) }}
          onKeyDown={(e) => { if (e.key === 'Enter') e.target.blur() }}
          placeholder="Nombre real del hablante…"
          className={inputCls}
        />
      </div>
      {speaker.clips?.length > 0 ? (
        <ul className="space-y-2">
          {speaker.clips.map((c, i) => (
            <li key={i} className="rounded-lg bg-slate-50 p-2">
              <div className="mb-1 flex items-center justify-between text-xs text-slate-500">
                <button onClick={() => onPlay(c.start, c.end)} className="text-blue-600 hover:underline">
                  ▶ {fmtTime(c.start)} – {fmtTime(c.end)}
                </button>
                <span>{Math.round(c.duration)}s</span>
              </div>
              {c.file && (
                <audio controls preload="none" src={`/api/projects/${projectId}/clips/${speaker.id}/${c.file}`} className="h-8 w-full" />
              )}
              <p className="mt-1 line-clamp-2 text-xs text-slate-600">“{c.text}”</p>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-xs text-slate-400">Sin clips aún: usa «Generar clips sugeridos».</p>
      )}
    </div>
  )
}

function TranscriptEditor({ projectId, segments, speakers, page, setPage, onPlay, reload, onError }) {
  const pages = Math.ceil(segments.length / PAGE_SIZE)
  const slice = segments.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE)
  const nameOf = (sid) => speakers.find((s) => s.id === sid)?.name || sid || '—'

  const saveSegment = async (seg, patch) => {
    try {
      await api.patch(`/projects/${projectId}/segments/${seg.id}`, patch)
    } catch (e) {
      onError(e.message)
    }
  }

  return (
    <div className="rounded-xl border border-slate-200 bg-white">
      <div className="flex items-center justify-between border-b border-slate-100 p-3">
        <h2 className="font-semibold">Transcripción ({segments.length} segmentos)</h2>
        <div className="flex items-center gap-2 text-sm">
          <button disabled={page === 0} onClick={() => setPage(page - 1)} className={btnSecondary}>←</button>
          <span className="text-slate-500">{page + 1}/{pages}</span>
          <button disabled={page >= pages - 1} onClick={() => setPage(page + 1)} className={btnSecondary}>→</button>
        </div>
      </div>
      <div className="divide-y divide-slate-100">
        {slice.map((seg) => (
          <div key={seg.id} className="flex items-start gap-2 p-2 hover:bg-slate-50">
            <button onClick={() => onPlay(seg.start, seg.end)} className="mt-1 shrink-0 text-blue-600 hover:underline" title="Escuchar">
              ▶
            </button>
            <span className="mt-1 w-20 shrink-0 text-xs tabular-nums text-slate-400">{fmtTime(seg.start)}</span>
            <select
              value={seg.speaker || ''}
              onChange={(e) => { seg.speaker = e.target.value; saveSegment(seg, { speaker: e.target.value }) }}
              className="mt-0.5 w-36 shrink-0 rounded border border-slate-300 bg-white px-1 py-1 text-xs"
            >
              <option value="">—</option>
              {speakers.map((s) => (
                <option key={s.id} value={s.id}>{s.name || s.id}</option>
              ))}
            </select>
            <SegmentText seg={seg} onSave={(text) => saveSegment(seg, { text })} />
          </div>
        ))}
      </div>
    </div>
  )
}

function SegmentText({ seg, onSave }) {
  const [text, setText] = useState(seg.text)
  const editing = useRef(false)
  useEffect(() => { if (!editing.current) setText(seg.text) }, [seg.text])

  return (
    <input
      value={text}
      onFocus={() => { editing.current = true }}
      onChange={(e) => setText(e.target.value)}
      onBlur={() => {
        editing.current = false
        if (text !== seg.text) onSave(text)
      }}
      onKeyDown={(e) => { if (e.key === 'Enter') e.target.blur() }}
      className={`w-full rounded px-2 py-1 text-sm outline-none focus:bg-blue-50 focus:ring-1 focus:ring-blue-300 ${
        seg.edited ? 'bg-amber-50' : ''
      }`}
    />
  )
}
