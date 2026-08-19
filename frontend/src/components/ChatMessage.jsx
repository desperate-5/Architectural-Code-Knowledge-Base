import Markdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

export default function ChatMessage({ message }) {
  const isUser = message.role === 'user'
  const isAssistant = message.role === 'assistant'
  const fromCache = isAssistant && message.from_cache

  return (
    <div className={`message ${isUser ? 'message-user' : 'message-assistant'}`}>
      <div className="message-avatar">{isUser ? '👤' : '🤖'}</div>
      <div className="message-body">
        <div className="message-name">{isUser ? '你' : '建筑规范助手'}</div>
        {fromCache ? (
          <div className="message-cache-badge">
            ⚡ 语义缓存命中
            {message.cache_similarity
              ? ` · 相似度 ${(message.cache_similarity * 100).toFixed(0)}%`
              : ''}
          </div>
        ) : (
          isAssistant &&
          message.model && (
            <div className="message-meta">
              模型: {message.model === 'semantic_cache' ? '语义缓存' : message.model}
            </div>
          )
        )}
        <div className={`message-content ${isAssistant ? 'markdown-body' : ''}`}>
          {isAssistant ? (
            message.content ? (
              <Markdown remarkPlugins={[remarkGfm]}>{message.content}</Markdown>
            ) : (
              '等待回答...'
            )
          ) : (
            message.content
          )}
        </div>
        {isAssistant && message.usage?.total_tokens && (
          <div className="message-usage">
            Token 用量: prompt={message.usage.prompt_tokens}, completion={message.usage.completion_tokens}, 总计={message.usage.total_tokens}
          </div>
        )}
      </div>
    </div>
  )
}
