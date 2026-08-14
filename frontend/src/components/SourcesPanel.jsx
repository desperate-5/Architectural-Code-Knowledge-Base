export default function SourcesPanel({ sources }) {
  if (!sources || sources.length === 0) return null

  return (
    <div className="sources-panel">
      <div className="sources-title">参考文档 ({sources.length} 篇)</div>
      <div className="sources-list">
        {sources.map((src, i) => (
          <details key={i} className="source-item">
            <summary className="source-summary">
              <span className="source-badge">{(src.channels || [src.source_type]).join(' + ')}</span>
              <span className="source-filename">{src.filename || '未知文件'}</span>
              <span className="source-score">{(src.score || 0).toFixed(2)}</span>
            </summary>
            <div className="source-text">{src.text || src.snippet}</div>
          </details>
        ))}
      </div>
    </div>
  )
}
