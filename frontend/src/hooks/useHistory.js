import { useState, useCallback } from 'react'

export function useHistory() {
  const [conversations, setConversations] = useState([])
  const [historyLoading, setHistoryLoading] = useState(false)

  const fetchList = useCallback(async () => {
    setHistoryLoading(true)
    try {
      const res = await fetch('/conversations?limit=50')
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = await res.json()
      setConversations(data)
    } catch (err) {
      console.error('加载历史失败', err)
    } finally {
      setHistoryLoading(false)
    }
  }, [])

  const saveConversation = useCallback(async ({ query, answer, sources, model }) => {
    try {
      await fetch('/conversations', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query, answer, sources, model }),
      })
      await fetchList()
    } catch (err) {
      console.error('保存历史失败', err)
    }
  }, [fetchList])

  const loadConversation = useCallback(async (id) => {
    try {
      const res = await fetch(`/conversations/${id}`)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      return await res.json()
    } catch (err) {
      console.error('加载对话失败', err)
      return null
    }
  }, [])

  const deleteConversation = useCallback(async (id) => {
    try {
      await fetch(`/conversations/${id}`, { method: 'DELETE' })
      await fetchList()
    } catch (err) {
      console.error('删除失败', err)
    }
  }, [fetchList])

  return {
    conversations,
    historyLoading,
    fetchList,
    saveConversation,
    loadConversation,
    deleteConversation,
  }
}
