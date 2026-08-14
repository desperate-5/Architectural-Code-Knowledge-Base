import { useState, useCallback } from 'react'

export function useDocuments() {
  const [documents, setDocuments] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const fetchList = useCallback(async () => {
    setLoading(true)
    try {
      const res = await fetch('/documents')
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = await res.json()
      setDocuments(data)
    } catch (err) {
      setError(`加载文档列表失败: ${err.message}`)
    } finally {
      setLoading(false)
    }
  }, [])

  const upload = useCallback(async (file, chunkSize, chunkOverlap) => {
    setError('')
    const form = new FormData()
    form.append('file', file)
    form.append('chunk_size', String(chunkSize))
    form.append('chunk_overlap', String(chunkOverlap))
    const res = await fetch('/documents', { method: 'POST', body: form })
    if (!res.ok) {
      const detail = await res.json().catch(() => ({}))
      throw new Error(detail.detail || `HTTP ${res.status}`)
    }
    return await res.json()
  }, [])

  const addDocument = useCallback((doc) => {
    setDocuments((prev) => [doc, ...prev.filter((d) => d.id !== doc.id)])
  }, [])

  const build = useCallback(async (id) => {
    setError('')
    const res = await fetch(`/documents/${id}/build`, { method: 'POST' })
    if (!res.ok) {
      const detail = await res.json().catch(() => ({}))
      throw new Error(detail.detail || `HTTP ${res.status}`)
    }
    return await res.json()
  }, [])

  const remove = useCallback(async (id) => {
    setError('')
    const res = await fetch(`/documents/${id}`, { method: 'DELETE' })
    if (!res.ok) {
      const detail = await res.json().catch(() => ({}))
      throw new Error(detail.detail || `HTTP ${res.status}`)
    }
    return await res.json()
  }, [])

  const fetchJob = useCallback(async (jobId) => {
    const res = await fetch(`/build/jobs/${jobId}`)
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    return await res.json()
  }, [])

  return { documents, loading, error, setError, fetchList, upload, addDocument, build, remove, fetchJob }
}
