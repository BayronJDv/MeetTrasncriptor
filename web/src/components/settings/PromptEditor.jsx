import React, { useState } from 'react'
import { api } from '../../api.js'
import { btnSecondary, inputCls } from '../../components.jsx'

const STAGES = [
  { label: 'Revisión', systemKey: 'review_system', userKey: 'review_user', variables: ['{{SEGMENTS}}', '{{MAX_SUGGESTIONS}}'] },
  { label: 'Estructura · parte 1', systemKey: 'meeting_1_system', userKey: 'meeting_1', variables: ['{{WIN_LO}}', '{{WIN_HI}}', '{{SEGMENTS}}'] },
  { label: 'Estructura · parte 2', systemKey: 'meeting_2_system', userKey: 'meeting_2', variables: ['{{PARTS}}'] },
  { label: 'Informe · parte 1', systemKey: 'report_1_system', userKey: 'report_1', variables: ['{{WIN_LO}}', '{{WIN_HI}}', '{{SEGMENTS}}'] },
  { label: 'Informe · parte 2', systemKey: 'report_2_system', userKey: 'report_2', variables: ['{{TEMPLATE_BLOCK}}', '{{MEETING_BLOCK}}', '{{NOTES}}', '{{INSTRUCTIONS_BLOCK}}'] },
]

export default function PromptEditor({ prompts, onChange }) {
  const [activeStage, setActiveStage] = useState(0)
  const [error, setError] = useState(null)
  const [restoring, setRestoring] = useState(false)
  const stage = STAGES[activeStage]
  const system = prompts?.[stage.systemKey]?.system || ''
  const user = prompts?.[stage.userKey]?.user || ''
  const combined = `${system}\n${user}`
  const missing = stage.variables.filter((variable) => {
    const name = variable.slice(2, -2)
    return !combined.includes(variable) && !combined.includes(`{${name.toLowerCase()}}`)
  })

  const updatePrompt = (key, part, value) => {
    onChange({
      ...prompts,
      [key]: { ...prompts?.[key], [part]: value },
    })
    setError(null)
  }

  const restoreDefaults = async () => {
    setRestoring(true)
    setError(null)
    try {
      const systemResult = await api.post(`/prompts/${stage.systemKey}/reset`)
      const userResult = await api.post(`/prompts/${stage.userKey}/reset`)
      onChange({ ...prompts, ...systemResult, ...userResult })
    } catch (e) {
      setError(e.message)
    } finally {
      setRestoring(false)
    }
  }

  return (
    <section className="rounded-xl border border-slate-200 bg-white p-4">
      <h2 className="mb-3 font-semibold">Editor de prompts</h2>
      <div className="mb-3 flex flex-wrap gap-2">
        {STAGES.map((item, index) => (
          <button key={item.label} type="button" onClick={() => setActiveStage(index)} className={btnSecondary} aria-pressed={activeStage === index}>
            {item.label}
          </button>
        ))}
      </div>
      <p className="mb-3 text-xs text-slate-500">Variables disponibles: {stage.variables.join(', ')}</p>
      <div className="grid gap-3 sm:grid-cols-2">
        <label className="block text-sm">
          <span className="mb-1 block font-medium text-slate-700">System</span>
          <textarea value={system} onChange={(e) => updatePrompt(stage.systemKey, 'system', e.target.value)} className={inputCls} rows={10} />
        </label>
        <label className="block text-sm">
          <span className="mb-1 block font-medium text-slate-700">User</span>
          <textarea value={user} onChange={(e) => updatePrompt(stage.userKey, 'user', e.target.value)} className={inputCls} rows={10} />
        </label>
      </div>
      {missing.length > 0 && <p className="mt-2 text-sm text-amber-700">Variables requeridas faltantes: {missing.join(', ')}</p>}
      {error && <p className="mt-2 text-sm text-red-700">No se pudieron restaurar los prompts: {error}</p>}
      <button type="button" onClick={restoreDefaults} disabled={restoring} className={`${btnSecondary} mt-3`}>
        {restoring ? 'Restaurando…' : 'Restaurar default'}
      </button>
    </section>
  )
}
