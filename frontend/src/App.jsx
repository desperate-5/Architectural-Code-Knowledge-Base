import { useRef, useEffect, useState } from 'react'
import { useAsk } from './hooks/useAsk'
import { useHistory } from './hooks/useHistory'
import ChatInput from './components/ChatInput'
import ChatMessage from './components/ChatMessage'
import ThinkingBar from './components/ThinkingBar'
import SourcesPanel from './components/SourcesPanel'
import ConversationSidebar from './components/ConversationSidebar'
import GraphView from './components/GraphView'
import DocumentManage from './components/DocumentManage'
import { useTheme } from './hooks/useTheme'

export default function App() {
  const [view, setView] = useState('chat')
  const [theme, toggleTheme] = useTheme()
  const history = useHistory()
  const { messages, loading, currentSteps, ask, reset, loadConversation } = useAsk(history.saveConversation)
  const bottomRef = useRef(null)

  useEffect(() => {
    history.fetchList()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, currentSteps])

  async function handleSelect(id) {
    const conv = await history.loadConversation(id)
    if (conv) loadConversation(conv)
  }

  return (
    <div className="app">
      <ConversationSidebar
        conversations={history.conversations}
        onNew={reset}
        onSelect={handleSelect}
        onDelete={history.deleteConversation}
      />

      <div className="app-main">
        <header className="header">
          <h1>Agentic RAG</h1>
          <p className="header-sub">建筑规范智能问答系统</p>
          <nav className="view-nav">
            <button
              className={view === 'chat' ? 'active' : ''}
              onClick={() => setView('chat')}
            >
              问答
            </button>
            <button
              className={view === 'graph' ? 'active' : ''}
              onClick={() => setView('graph')}
            >
              知识图谱
            </button>
            <button
              className={view === 'documents' ? 'active' : ''}
              onClick={() => setView('documents')}
            >
              文档管理
            </button>
          </nav>
          <button
            className="theme-toggle"
            onClick={toggleTheme}
            title={theme === 'dark' ? '切换到浅色模式' : '切换到深色模式'}
            aria-label="切换明暗模式"
          >
            {theme === 'dark' ? (
              <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="5" />
                <line x1="12" y1="1" x2="12" y2="3" />
                <line x1="12" y1="21" x2="12" y2="23" />
                <line x1="4.22" y1="4.22" x2="5.64" y2="5.64" />
                <line x1="18.36" y1="18.36" x2="19.78" y2="19.78" />
                <line x1="1" y1="12" x2="3" y2="12" />
                <line x1="21" y1="12" x2="23" y2="12" />
                <line x1="4.22" y1="19.78" x2="5.64" y2="18.36" />
                <line x1="18.36" y1="5.64" x2="19.78" y2="4.22" />
              </svg>
            ) : (
              <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
              </svg>
            )}
          </button>
        </header>

        {view === 'graph' ? (
          <main className="main graph-main">
            <GraphView theme={theme} />
          </main>
        ) : view === 'documents' ? (
          <main className="main doc-main">
            <DocumentManage />
          </main>
        ) : (
          <>
            <main className="main">
              {messages.length === 0 ? (
                <div className="welcome">
                  <div className="welcome-icon">🏗️</div>
                  <h2>建筑规范问答助手</h2>
                  <p>输入建筑规范相关的问题，AI 将自动判断是否需要检索规范文档，并给出带来源引用的专业回答。</p>
                  <div className="welcome-hints">
                    <div className="hint" onClick={() => ask('住宅建筑的防火极限是多少？')}>
                      住宅建筑的防火极限是多少？
                    </div>
                    <div className="hint" onClick={() => ask('9层住宅的耐火等级、疏散宽度和消防电梯有哪些综合要求？')}>
                      9层住宅的耐火等级、疏散宽度和消防电梯有哪些综合要求？
                    </div>
                    <div className="hint" onClick={() => ask('高层住宅在消防设计方面需要注意哪些变化和趋势？')}>
                      高层住宅在消防设计方面需要注意哪些变化和趋势？
                    </div>
                  </div>
                </div>
              ) : (
                <div className="chat-area">
                  {messages.map((msg, i) => {
                    const isLastAssistant = msg.role === 'assistant' && i === messages.length - 1
                    return (
                      <div key={i}>
                        {loading && isLastAssistant && (
                          <ThinkingBar step={currentSteps[currentSteps.length - 1]} />
                        )}
                        <ChatMessage message={msg} />
                        {isLastAssistant && msg.content && (
                          <SourcesPanel sources={msg.sources} />
                        )}
                      </div>
                    )
                  })}
                  <div ref={bottomRef} />
                </div>
              )}
            </main>

            <footer className="footer">
              <ChatInput onSend={ask} loading={loading} />
            </footer>
          </>
        )}
      </div>
    </div>
  )
}
