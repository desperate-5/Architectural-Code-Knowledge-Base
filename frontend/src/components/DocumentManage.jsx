import { useEffect, useRef, useState } from 'react'
import { useDocuments } from '../hooks/useDocuments'

const STATUS_LABELS = {
  uploaded: '已上传',
  building: '构建中',
  indexed: '已索引',
  error: '失败',
}

const STAGE_LABELS = {
  parse: '解析 (PDF → Markdown)',
  keyword: '关键词索引',
  vector: '向量索引',
  graph: '知识图谱',
}

export default function DocumentManage() {
  const { documents, loading, error, setError, fetchList, upload, addDocument, build, remove, fetchJob } = useDocuments()
  const [file, setFile] = useState(null)
  const [chunkSize, setChunkSize] = useState(512)
  const [chunkOverlap, setChunkOverlap] = useState(64)
  const [uploading, setUploading] = useState(false)
  const [job, setJob] = useState(null)
  const [activeJobId, setActiveJobId] = useState(null)
  const timerRef = useRef(null)

  // 待构建文档：从持久化列表中取最近一个 uploaded/error 状态的文档（列表按 created_at DESC 排序）
  const pendingDoc = documents.find((d) => d.status === 'uploaded' || d.status === 'error') || null

  useEffect(() => {
    fetchList()
  }, [fetchList])

  useEffect(() => {
    if (!activeJobId) return
    const tick = async () => {
      try {
        const j = await fetchJob(activeJobId)
        setJob(j)
        if (j.status === 'done' || j.status === 'error') {
          stopPolling()
          fetchList()
        }
      } catch (_) {
        // 忽略瞬时网络错误，继续轮询
      }
    }
    tick()
    timerRef.current = setInterval(tick, 1000)
    return () => {
      if (timerRef.current) clearInterval(timerRef.current)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeJobId])

  function stopPolling() {
    if (timerRef.current) clearInterval(timerRef.current)
    timerRef.current = null
    setActiveJobId(null)
  }

  async function handleUpload(e) {
    e.preventDefault()
    if (!file) {
      setError('请先选择 PDF 文件')
      return
    }
    setUploading(true)
    setError('')
    try {
      const doc = await upload(file, chunkSize, chunkOverlap)
      setFile(null)
      e.target.reset()
      stopPolling()
      setJob(null)
      addDocument(doc)
      await fetchList()
    } catch (err) {
      setError(err.message)
    } finally {
      setUploading(false)
    }
  }

  async function handleBuildPending() {
    if (!pendingDoc) return
    setError('')
    try {
      const { job_id } = await build(pendingDoc.id)
      setJob(null)
      setActiveJobId(job_id)
      await fetchList()
    } catch (err) {
      setError(err.message)
    }
  }

  async function handleDelete(doc) {
    if (!window.confirm(`确认删除「${doc.filename}」？删除后会重建索引。`)) return
    setError('')
    try {
      const { job_id } = await remove(doc.id)
      await fetchList()
      setJob(null)
      setActiveJobId(job_id)
    } catch (err) {
      setError(err.message)
    }
  }

  function formatTime(iso) {
    if (!iso) return '-'
    return new Date(iso).toLocaleString()
  }

  const stages = job?.stages || {}

  return (
    <div className="doc-manage">
      <section className="doc-card">
        <h2 className="doc-section-title">上传文档</h2>
        <form className="doc-upload-form" onSubmit={handleUpload}>
          <input
            type="file"
            accept=".pdf,application/pdf"
            onChange={(e) => setFile(e.target.files?.[0] || null)}
          />
          <label className="doc-field">
            分块大小（字符）
            <input
              type="number"
              min="100"
              step="1"
              value={chunkSize}
              onChange={(e) => setChunkSize(Number(e.target.value))}
            />
          </label>
          <label className="doc-field">
            重叠（字符）
            <input
              type="number"
              min="0"
              step="1"
              value={chunkOverlap}
              onChange={(e) => setChunkOverlap(Number(e.target.value))}
            />
          </label>
          <button type="submit" disabled={uploading || !file}>
            {uploading ? '上传中…' : '上传'}
          </button>
          <button type="button" disabled={!pendingDoc || !!activeJobId} onClick={handleBuildPending}>
            构建索引
          </button>
        </form>
      </section>

      {job && (
        <section className="doc-card">
          <h2 className="doc-section-title">构建进度</h2>
          <div className="doc-overall">
            <div className="doc-overall-bar">
              <div className="doc-overall-fill" style={{ width: `${job.overall_percent}%` }} />
            </div>
            <span className="doc-overall-text">{job.overall_percent}%</span>
          </div>
          <div className="doc-stage-list">
            {Object.entries(STAGE_LABELS).map(([stage, label]) => {
              const s = stages[stage] || { percent: 0, message: '' }
              return (
                <div className="doc-stage" key={stage}>
                  <div className="doc-stage-head">
                    <span>{label}</span>
                    <span className="doc-stage-pct">{s.percent}%</span>
                  </div>
                  <div className="doc-stage-bar">
                    <div className="doc-stage-fill" style={{ width: `${s.percent}%` }} />
                  </div>
                  {s.message && <div className="doc-stage-msg">{s.message}</div>}
                </div>
              )
            })}
          </div>
          {job.status === 'done' && <div className="doc-job-done">构建完成 ✓</div>}
          {job.status === 'error' && <div className="doc-job-error">构建失败：{job.message}</div>}
        </section>
      )}

      <section className="doc-card">
        <h2 className="doc-section-title">已有文档</h2>
        {error && <div className="doc-error">{error}</div>}
        {loading && documents.length === 0 ? (
          <div className="doc-empty">加载中…</div>
        ) : documents.length === 0 ? (
          <div className="doc-empty">暂无文档，请先上传 PDF</div>
        ) : (
          <table className="doc-table">
            <thead>
              <tr>
                <th>文件名</th>
                <th>状态</th>
                <th>分块大小</th>
                <th>重叠</th>
                <th>chunk 数</th>
                <th>创建时间</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {documents.map((d) => (
                <tr key={d.id}>
                  <td className="doc-name">{d.filename}</td>
                  <td>
                    <span className={`doc-status doc-status-${d.status}`}>
                      {STATUS_LABELS[d.status] || d.status}
                    </span>
                  </td>
                  <td>{d.chunk_size}</td>
                  <td>{d.chunk_overlap}</td>
                  <td>{d.chunk_count}</td>
                  <td>{formatTime(d.created_at)}</td>
                  <td className="doc-actions">
                    <button className="doc-btn doc-btn-danger" onClick={() => handleDelete(d)}>
                      删除
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  )
}
