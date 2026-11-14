import React from 'react'
import { Link, NavLink, Outlet, useParams } from 'react-router-dom'
import { JobBanner, JobProvider } from './components.jsx'

const TABS = [
  { slug: 'proceso', label: '1 · Transcripción' },
  { slug: 'hablantes', label: '2 · Hablantes' },
  { slug: 'revision', label: '3 · Revisión IA' },
  { slug: 'reunion', label: '4 · Estructura' },
  { slug: 'informe', label: '5 · Informe' },
]

export default function App() {
  const { projectId } = useParams()

  return (
    <JobProvider projectId={projectId}>
      <div className="min-h-screen bg-slate-50 text-slate-900">
        <header className="border-b border-slate-200 bg-white">
          <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3">
            <Link to="/" className="text-lg font-bold text-blue-700">
              🎙 Transcriptor de reuniones
            </Link>
            <Link to="/ajustes" className="text-sm font-medium text-slate-600 hover:text-blue-700">
              ⚙ Ajustes
            </Link>
          </div>
        </header>

        <main className="mx-auto max-w-6xl px-4 py-6">
          <nav className="mb-4 flex flex-wrap gap-1">
            {TABS.map((t) => (
              <NavLink
                key={t.slug}
                to={`/p/${projectId}/${t.slug}`}
                className={({ isActive }) =>
                  `rounded-md px-3 py-1.5 text-sm font-medium ${
                    isActive ? 'bg-blue-600 text-white' : 'text-slate-600 hover:bg-slate-200'
                  }`
                }
              >
                {t.label}
              </NavLink>
            ))}
          </nav>

          <div className="mb-4">
            <JobBanner />
          </div>

          <Outlet />
        </main>
      </div>
    </JobProvider>
  )
}
