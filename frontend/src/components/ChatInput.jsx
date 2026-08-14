import { useState } from 'react'

export default function ChatInput({ onSend, loading }) {
  const [text, setText] = useState('')

  function handleSubmit(e) {
    e.preventDefault()
    if (!text.trim() || loading) return
    onSend(text.trim())
    setText('')
  }

  return (
    <form onSubmit={handleSubmit} className="chat-input">
      <input
        type="text"
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder="输入建筑规范相关的问题..."
        disabled={loading}
        className="chat-input-field"
      />
      <button type="submit" disabled={loading || !text.trim()} className="chat-send-btn">
        {loading ? '思考中...' : '发送'}
      </button>
    </form>
  )
}
