import React from 'react'
import ReactDOM from 'react-dom/client'
import { createBrowserRouter, RouterProvider } from 'react-router-dom'
import './index.css'
import App from './App.jsx'
import ProjectsPage from './pages/Projects.jsx'
import ProcessPage from './pages/Process.jsx'
import SpeakersPage from './pages/Speakers.jsx'
import ReviewPage from './pages/Review.jsx'
import MeetingPage from './pages/Meeting.jsx'
import ReportPage from './pages/Report.jsx'
import SettingsPage from './pages/Settings.jsx'

const router = createBrowserRouter([
  { path: '/', element: <ProjectsPage /> },
  {
    path: '/p/:projectId',
    element: <App />,
    children: [
      { index: true, element: <ProcessPage /> },
      { path: 'proceso', element: <ProcessPage /> },
      { path: 'hablantes', element: <SpeakersPage /> },
      { path: 'revision', element: <ReviewPage /> },
      { path: 'reunion', element: <MeetingPage /> },
      { path: 'informe', element: <ReportPage /> },
    ],
  },
  { path: '/ajustes', element: <SettingsPage /> },
])

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <RouterProvider router={router} />
  </React.StrictMode>,
)
