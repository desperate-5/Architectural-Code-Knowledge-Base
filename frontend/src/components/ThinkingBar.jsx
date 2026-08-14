const NODE_ICONS = {
  classify: '🧠',
  direct_answer: '💬',
  optimize_query: '🔧',
  retrieve: '🔍',
  evaluate: '✅',
  expand_query: '📎',
  process_documents: '📋',
  generate: '✍️',
}

export default function ThinkingBar({ step }) {
  const icon = step ? (NODE_ICONS[step.node] || '⚙️') : '💭'
  const title = step?.title || '正在思考'
  const desc = step?.desc || '正在分析问题...'

  return (
    <div className="thinking-bar">
      <span className="thinking-spinner" />
      <span className="thinking-icon">{icon}</span>
      <span className="thinking-title">{title}</span>
      <span className="thinking-desc">{desc}</span>
    </div>
  )
}
