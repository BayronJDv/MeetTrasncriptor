const BASE = '/api'

async function request(method, path, body, isJson = true) {
  const opts = { method, headers: {} }
  if (body !== undefined) {
    if (body instanceof FormData) {
      opts.body = body
    } else if (isJson) {
      opts.headers['Content-Type'] = 'application/json'
      opts.body = JSON.stringify(body)
    } else {
      opts.body = body
    }
  }
  const res = await fetch(BASE + path, opts)
  if (!res.ok) {
    let detail = `HTTP ${res.status}`
    try {
      const data = await res.json()
      detail = data.detail || detail
    } catch { /* respuesta sin JSON */ }
    throw new Error(detail)
  }
  const ct = res.headers.get('content-type') || ''
  return ct.includes('application/json') ? res.json() : res.text()
}

export const api = {
  get: (p) => request('GET', p),
  post: (p, body) => request('POST', p, body),
  put: (p, body) => request('PUT', p, body),
  patch: (p, body) => request('PATCH', p, body),
  del: (p) => request('DELETE', p),
}

export function uploadWithProgress(path, formData, onProgress) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    xhr.open('POST', BASE + path)
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable && onProgress) onProgress(Math.round((e.loaded / e.total) * 100))
    }
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        try { resolve(JSON.parse(xhr.responseText)) } catch { resolve(xhr.responseText) }
      } else {
        let detail = `HTTP ${xhr.status}`
        try { detail = JSON.parse(xhr.responseText).detail || detail } catch { /* sin JSON */ }
        reject(new Error(detail))
      }
    }
    xhr.onerror = () => reject(new Error('Error de red durante la subida'))
    xhr.send(formData)
  })
}

export function fmtTime(seconds) {
  if (seconds == null || Number.isNaN(seconds)) return '—'
  const s = Math.max(0, Math.floor(seconds))
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  const sec = s % 60
  const mm = String(h > 0 ? m : m).padStart(2, '0')
  return (h > 0 ? `${h}:${mm}` : `${m}`) + `:${String(sec).padStart(2, '0')}`
}

export function fmtDuration(seconds) {
  if (!seconds) return '—'
  const h = Math.floor(seconds / 3600)
  const m = Math.round((seconds % 3600) / 60)
  return h > 0 ? `${h} h ${m} min` : `${m} min`
}
