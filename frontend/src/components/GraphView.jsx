import { useEffect, useRef, useState } from 'react'
import * as echarts from 'echarts'

function mergeGraph(current, incoming) {
  const nodeMap = {}
  for (const n of current.nodes) nodeMap[n.id] = n
  for (const n of incoming.nodes || []) {
    if (!nodeMap[n.id]) nodeMap[n.id] = n
  }

  const edges = [...current.edges]
  const edgeKeys = new Set(edges.map((e) => `${e.source}|${e.target}|${e.type}`))
  for (const e of incoming.edges || []) {
    const key = `${e.source}|${e.target}|${e.type}`
    if (!edgeKeys.has(key)) {
      edgeKeys.add(key)
      edges.push(e)
    }
  }

  return { nodes: Object.values(nodeMap), edges }
}

export default function GraphView({ theme = 'light' }) {
  const canvasRef = useRef(null)
  const chartRef = useRef(null)
  const [query, setQuery] = useState('')
  const [results, setResults] = useState([])
  const [graph, setGraph] = useState({ nodes: [], edges: [] })
  const [selectedEdge, setSelectedEdge] = useState(null)
  const [selectedNode, setSelectedNode] = useState(null)
  const [message, setMessage] = useState('')
  const [loading, setLoading] = useState(false)
  const isDark = theme === 'dark'

  useEffect(() => {
    if (!canvasRef.current) return
    const chart = echarts.init(canvasRef.current)
    chartRef.current = chart
    const onResize = () => chart.resize()
    window.addEventListener('resize', onResize)
    return () => {
      window.removeEventListener('resize', onResize)
      chart.dispose()
      chartRef.current = null
    }
  }, [])

  useEffect(() => {
    const chart = chartRef.current
    if (!chart) return

    const labels = [...new Set(graph.nodes.map((n) => n.label).filter(Boolean))]
    const categories = labels.map((name) => ({ name }))

    chart.setOption(
      {
        tooltip: {
          backgroundColor: isDark ? '#1f2937' : '#ffffff',
          borderColor: isDark ? '#374151' : '#e5e7eb',
          textStyle: { color: isDark ? '#e5e7eb' : '#1f2937' },
          formatter: (p) =>
            p.dataType === 'edge'
              ? `${p.data.type || '关系'}`
              : `${p.data.name}<br/>类型: ${p.data.label || '-'}`,
        },
        legend: categories.length
          ? [{ data: categories.map((c) => c.name), type: 'scroll', top: 8, textStyle: { color: isDark ? '#e5e7eb' : '#1f2937' } }]
          : [],
        series: [
          {
            type: 'graph',
            layout: 'force',
            roam: true,
            draggable: true,
            categories,
            data: graph.nodes.map((n) => ({
              id: n.id,
              name: n.name,
              category: labels.indexOf(n.label),
              label: n.label,
              sources: n.sources,
              symbolSize: 28,
            })),
            links: graph.edges.map((e) => ({
              source: e.source,
              target: e.target,
              type: e.type,
              sources: e.sources,
            })),
            label: { show: true, position: 'right', fontSize: 12, color: isDark ? '#e5e7eb' : '#1f2937' },
            force: { repulsion: 220, edgeLength: 120 },
            lineStyle: { color: isDark ? '#64748b' : '#94a3b8', curveness: 0.1 },
            emphasis: { focus: 'adjacency', lineStyle: { width: 3 } },
          },
        ],
      },
      true
    )

    chart.off('click')
    chart.on('click', (params) => {
      if (params.dataType === 'edge') {
        setSelectedNode(null)
        setSelectedEdge(params.data)
      } else if (params.dataType === 'node') {
        setSelectedEdge(null)
        setSelectedNode(params.data)
      }
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [graph, theme])

  useEffect(() => {
    loadFullGraph()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  async function loadFullGraph() {
    setResults([])
    setSelectedEdge(null)
    setSelectedNode(null)
    setMessage('')
    setLoading(true)
    try {
      const res = await fetch('/graph/all')
      const data = await res.json()
      setGraph(data || { nodes: [], edges: [] })
      if (!data || data.nodes.length === 0) setMessage('图谱暂无数据')
    } catch (err) {
      setMessage(`加载失败: ${err.message}`)
    } finally {
      setLoading(false)
    }
  }

  async function expandNode(name) {
    try {
      const res = await fetch(`/graph/entity?name=${encodeURIComponent(name)}`)
      const data = await res.json()
      if (data) setGraph((prev) => mergeGraph(prev, data))
    } catch (err) {
      console.error('expandNode failed', err)
    }
  }

  async function searchEntities(e) {
    e?.preventDefault()
    const q = query.trim()
    if (!q) return
    setLoading(true)
    try {
      const res = await fetch(`/graph/search?q=${encodeURIComponent(q)}`)
      const data = await res.json()
      setResults(data || [])
      setMessage(data && data.length === 0 ? '未找到相关实体' : '')
    } catch (err) {
      setMessage(`搜索失败: ${err.message}`)
    } finally {
      setLoading(false)
    }
  }

  async function loadEntity(name) {
    setResults([])
    setSelectedEdge(null)
    setSelectedNode(null)
    setMessage('')
    setLoading(true)
    try {
      const res = await fetch(`/graph/entity?name=${encodeURIComponent(name)}`)
      const data = await res.json()
      setGraph(data || { nodes: [], edges: [] })
      if (!data || data.nodes.length === 0) setMessage('该实体没有邻居关系')
    } catch (err) {
      setMessage(`加载失败: ${err.message}`)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="graph-view">
      <div className="graph-toolbar">
        <form className="graph-search" onSubmit={searchEntities}>
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="搜索实体，如：耐火等级"
          />
          <button type="submit" disabled={loading}>搜索</button>
          <button type="button" className="graph-overview-btn" onClick={loadFullGraph} disabled={loading}>总览</button>
        </form>
        {results.length > 0 && (
          <ul className="graph-search-results">
            {results.map((r) => (
              <li key={r.name} onClick={() => loadEntity(r.name)}>
                <span className="graph-result-name">{r.name}</span>
                <span className="graph-result-label">{r.label}</span>
              </li>
            ))}
          </ul>
        )}
      </div>

      {message && <div className="graph-message">{message}</div>}

      <div className="graph-canvas" ref={canvasRef} />

      {selectedEdge && (
        <div className="graph-edge-panel">
          <button className="graph-edge-close" onClick={() => setSelectedEdge(null)}>×</button>
          <h4>关系: {selectedEdge.type}</h4>
          <div className="graph-edge-path">{selectedEdge.source} → {selectedEdge.target}</div>
          {(selectedEdge.sources || []).length > 0 ? (
            <ul className="graph-edge-sources">
              {selectedEdge.sources.map((s, i) => (
                <li key={i}>
                  {[s.filename, s.chapter, s.section, s.clause].filter(Boolean).join(' · ')}
                </li>
              ))}
            </ul>
          ) : (
            <div className="graph-edge-empty">无条款来源</div>
          )}
        </div>
      )}

      {selectedNode && (
        <div className="graph-edge-panel">
          <button className="graph-edge-close" onClick={() => setSelectedNode(null)}>×</button>
          <h4>{selectedNode.name}</h4>
          <div className="graph-node-label">类型: {selectedNode.label || '-'}</div>
          <button
            className="graph-expand-btn"
            onClick={() => expandNode(selectedNode.name)}
          >
            展开邻居
          </button>
          {(selectedNode.sources || []).length > 0 ? (
            <ul className="graph-edge-sources">
              {selectedNode.sources.map((s, i) => (
                <li key={i}>
                  {[s.filename, s.chapter, s.section, s.clause].filter(Boolean).join(' · ')}
                </li>
              ))}
            </ul>
          ) : (
            <div className="graph-edge-empty">无条款来源</div>
          )}
        </div>
      )}
    </div>
  )
}
