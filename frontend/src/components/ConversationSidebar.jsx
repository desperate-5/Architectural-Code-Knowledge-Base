function formatTime(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  return d.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export default function ConversationSidebar({ conversations, onNew, onSelect, onDelete }) {
  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        <h2>历史对话</h2>
        <button className="sidebar-new" onClick={onNew}>+ 新对话</button>
      </div>
      <div className="sidebar-list">
        {conversations.length === 0 ? (
          <div className="sidebar-empty">暂无历史记录</div>
        ) : (
          conversations.map((c) => (
            <div key={c.id} className="sidebar-item" onClick={() => onSelect(c.id)}>
              <div className="sidebar-item-title">{c.title}</div>
              <div className="sidebar-item-time">{formatTime(c.created_at)}</div>
              <button
                className="sidebar-item-delete"
                title="删除"
                onClick={(e) => { e.stopPropagation(); onDelete(c.id) }}
              >
                ×
              </button>
            </div>
          ))
        )}
      </div>
    </aside>
  )
}
