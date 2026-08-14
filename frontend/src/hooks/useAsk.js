import { useState, useRef, useCallback } from 'react'
import { flushSync } from 'react-dom'

const NODE_LABELS = {
  classify: { title: '意图分类', desc: '判断是否需要检索' },
  direct_answer: { title: '直接回答', desc: '无检索，直接回答' },
  optimize_query: { title: '查询优化', desc: '清洗 → 关键词 → 改写' },
  retrieve: { title: '检索', desc: '向量 + 关键词融合' },
  evaluate: { title: '质量评估', desc: '评估检索结果是否充足' },
  expand_query: { title: '扩展查询', desc: '生成同义 / 上下位查询' },
  process_documents: { title: '文档后处理', desc: '排序去重' },
  generate: { title: '答案生成', desc: 'LLM 生成最终回答' },
}

export function useAsk(onSaved) {
  const [messages, setMessages] = useState([])
  const [loading, setLoading] = useState(false)
  const [currentSteps, setCurrentSteps] = useState([])
  const abortRef = useRef(null)

  const ask = useCallback(async (query) => {
    if (loading) return
    setLoading(true)
    setCurrentSteps([])

    const userMsg = { role: 'user', content: query }
    const assistantMsg = { role: 'assistant', content: '', steps: [], sources: [], model: '', usage: {} }
    flushSync(() => setMessages([userMsg, assistantMsg]))

    try {
      const res = await fetch('/ask/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query }),
      })

      if (!res.ok) throw new Error(`HTTP ${res.status}`)

      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const parts = buffer.split('\n\n')
        buffer = parts.pop() || ''

        for (const part of parts) {
          if (!part.startsWith('data: ')) continue
          const data = JSON.parse(part.slice(6))

          if (data.type === 'error') {
            setMessages((prev) => {
              const updated = prev.map((m, i) =>
                i === prev.length - 1 && m.role === 'assistant'
                  ? { ...m, content: `后端错误：${data.message}` }
                  : m
              )
              return updated
            })
            break
          } else if (data.type === 'token') {
            flushSync(() =>
              setMessages((prev) => {
                const idx = prev.length - 1
                if (idx < 0 || prev[idx].role !== 'assistant') return prev
                const updated = [...prev]
                updated[idx] = { ...updated[idx], content: (updated[idx].content || '') + data.content }
                return updated
              })
            )
          } else if (data.type === 'done') {
            setMessages((prev) => {
              const idx = prev.length - 1
              if (idx < 0 || prev[idx].role !== 'assistant') return prev
              const updated = [...prev]
              updated[idx] = {
                ...updated[idx],
                sources: data.sources || [],
                model: data.model || '',
                usage: data.usage || {},
              }
              return updated
            })
            if (onSaved) {
              onSaved({ query, answer: data.answer || '', sources: data.sources || [], model: data.model || '' })
            }
          } else if (data.type === 'step') {
            setCurrentSteps((prev) => [...prev, {
              node: 'generate',
              title: '答案生成 (流式)',
              desc: 'LLM 逐 token 生成最终回答',
              ...data.details,
            }])
          } else {
            const label = NODE_LABELS[data.node] || { title: data.node, desc: data.description }
            setCurrentSteps((prev) => {
              const exists = prev.find((s) => s.node === data.node)
              if (exists) {
                return prev.map((s) => (s.node === data.node ? { ...s, ...data.details } : s))
              }
              return [...prev, { node: data.node, title: label.title, desc: label.desc, ...data.details }]
            })
          }
        }
      }
    } catch (err) {
      if (err.name !== 'AbortError') {
        const errMsg = `请求失败：${err.message}`
        setMessages((prev) => {
          const idx = prev.length - 1
          if (idx < 0 || prev[idx].role !== 'assistant') return prev
          const updated = [...prev]
          updated[idx] = { ...updated[idx], content: errMsg }
          return updated
        })
      }
    } finally {
      setLoading(false)
      setCurrentSteps([])
    }
  }, [loading, onSaved])

  const reset = useCallback(() => {
    setMessages([])
    setCurrentSteps([])
  }, [])

  const loadConversation = useCallback((conv) => {
    if (!conv || !conv.messages) return
    const msgs = conv.messages.map((m) => ({
      role: m.role,
      content: m.content,
      sources: m.sources || [],
      model: m.model || '',
      usage: {},
    }))
    setMessages(msgs)
    setCurrentSteps([])
  }, [])

  return { messages, loading, currentSteps, ask, reset, loadConversation }
}
