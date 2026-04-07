import { useMemo, useState } from 'react'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
  ResponsiveContainer,
} from 'recharts'
import type { Message, PersonaSummary } from '../services/api'
import './EmotionCurve.css'

interface Props {
  open: boolean
  onClose: () => void
  messages: Message[]
  personaMap: Record<string, PersonaSummary>
}

interface DataPoint {
  index: number
  [personaId: string]: number | string | null
}

interface TurningPoint {
  personaId: string
  index: number
  prevScore: number
  score: number
  label: string | null
  summary: string
}



interface HeatmapCell {
  personaId: string
  index: number
  score: number | null
  label: string | null
  summary: string
}

// ---------------------------------------------------------------------------
// Pure helpers
// ---------------------------------------------------------------------------

function linearRegression(points: { x: number; y: number }[]): { k: number; b: number } {
  const n = points.length
  if (n < 2) return { k: 0, b: points[0]?.y ?? 0 }
  const sumX = points.reduce((s, p) => s + p.x, 0)
  const sumY = points.reduce((s, p) => s + p.y, 0)
  const sumXY = points.reduce((s, p) => s + p.x * p.y, 0)
  const sumX2 = points.reduce((s, p) => s + p.x * p.x, 0)
  const denom = n * sumX2 - sumX * sumX
  if (denom === 0) return { k: 0, b: sumY / n }
  const k = (n * sumXY - sumX * sumY) / denom
  const b = (sumY - k * sumX) / n
  return { k, b }
}

function scoreToColor(score: number | null): string {
  if (score == null) return '#f3f4f6'
  const t = Math.max(0, Math.min(1, (score + 5) / 10))
  // red(-5) → yellow(0) → green(+5)
  if (t < 0.5) {
    const r = 239
    const g = Math.round(68 + t * 2 * (191 - 68))
    const b = 68
    return `rgb(${r},${g},${b})`
  }
  const r = Math.round(239 - (t - 0.5) * 2 * (239 - 34))
  const g = Math.round(191 + (t - 0.5) * 2 * (197 - 191))
  const b = Math.round(68 + (t - 0.5) * 2 * (94 - 68))
  return `rgb(${r},${g},${b})`
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function EmotionCurve({ open, onClose, messages, personaMap }: Props) {
  const [tab, setTab] = useState<'curve' | 'heatmap'>('curve')
  const [hoverCell, setHoverCell] = useState<HeatmapCell | null>(null)

  const { data, personaIds, turningPoints, trendData, heatmapRows, maxIndex } = useMemo(() => {
    const personaMsgs = messages.filter(
      (m) => m.sender_type === 'persona' && m.emotion_score != null,
    )
    if (personaMsgs.length === 0)
      return {
        data: [] as DataPoint[],
        personaIds: [] as string[],
        turningPoints: [] as TurningPoint[],
        trendData: [] as DataPoint[],
        heatmapRows: [] as { personaId: string; cells: HeatmapCell[] }[],
        maxIndex: 0,
      }

    const ids = new Set<string>()
    const points: DataPoint[] = []
    // Per-persona score sequence for turning point + trend detection
    const perPersona: Record<string, { index: number; score: number; label: string | null; summary: string }[]> = {}

    let seq = 0
    for (const msg of personaMsgs) {
      ids.add(msg.sender_id)
      seq++
      const pt: DataPoint = { index: seq }
      pt[msg.sender_id] = msg.emotion_score
      pt[`${msg.sender_id}_label`] = msg.emotion_label
      pt[`${msg.sender_id}_summary`] = msg.content.slice(0, 30)
      points.push(pt)

      if (!perPersona[msg.sender_id]) perPersona[msg.sender_id] = []
      perPersona[msg.sender_id].push({
        index: seq,
        score: msg.emotion_score!,
        label: msg.emotion_label,
        summary: msg.content.slice(0, 40),
      })
    }

    const pids = Array.from(ids)

    // --- Turning points: score change >= 3 ---
    const tps: TurningPoint[] = []
    for (const pid of pids) {
      const seq2 = perPersona[pid]
      for (let i = 1; i < seq2.length; i++) {
        const diff = Math.abs(seq2[i].score - seq2[i - 1].score)
        if (diff >= 3) {
          tps.push({
            personaId: pid,
            index: seq2[i].index,
            prevScore: seq2[i - 1].score,
            score: seq2[i].score,
            label: seq2[i].label,
            summary: seq2[i].summary,
          })
        }
      }
    }

    // --- Trend lines (linear regression, >= 3 points) ---
    const trendPts: DataPoint[] = []
    for (const pid of pids) {
      const seq2 = perPersona[pid]
      if (seq2.length < 3) continue
      const regPoints = seq2.map((s) => ({ x: s.index, y: s.score }))
      const { k, b } = linearRegression(regPoints)
      const first = seq2[0].index
      const last = seq2[seq2.length - 1].index
      // Add two points for the trend line
      const existing1 = trendPts.find((p) => p.index === first)
      const existing2 = trendPts.find((p) => p.index === last)
      if (existing1) {
        existing1[`${pid}_trend`] = k * first + b
      } else {
        const tp: DataPoint = { index: first }
        tp[`${pid}_trend`] = k * first + b
        trendPts.push(tp)
      }
      if (existing2) {
        existing2[`${pid}_trend`] = k * last + b
      } else {
        const tp: DataPoint = { index: last }
        tp[`${pid}_trend`] = k * last + b
        trendPts.push(tp)
      }
    }
    trendPts.sort((a, b) => a.index - b.index)

    // --- Heatmap rows ---
    const rows = pids.map((pid) => {
      const seqMap = new Map(perPersona[pid].map((s) => [s.index, s]))
      const cells: HeatmapCell[] = []
      for (let i = 1; i <= seq; i++) {
        const item = seqMap.get(i)
        cells.push({
          personaId: pid,
          index: i,
          score: item?.score ?? null,
          label: item?.label ?? null,
          summary: item?.summary ?? '',
        })
      }
      return { personaId: pid, cells }
    })

    return {
      data: points,
      personaIds: pids,
      turningPoints: tps,
      trendData: trendPts,
      heatmapRows: rows,
      maxIndex: seq,
    }
  }, [messages])

  if (!open) return null

  // Build a lookup for turning points
  const tpLookup = new Set(turningPoints.map((tp) => `${tp.personaId}:${tp.index}`))

  // Custom dot renderer: highlight turning points
  const renderDot = (pid: string) => (props: any) => {
    const { cx, cy, index: _idx, payload } = props
    if (cx == null || cy == null) return null
    const seq = payload?.index
    const isTp = tpLookup.has(`${pid}:${seq}`)
    if (isTp) {
      const tp = turningPoints.find((t) => t.personaId === pid && t.index === seq)
      const rising = tp ? tp.score > tp.prevScore : false
      return (
        <g key={`tp-${pid}-${seq}`}>
          <circle cx={cx} cy={cy} r={8} fill="#fff" stroke="#ef4444" strokeWidth={2} />
          <text x={cx} y={cy + 4} textAnchor="middle" fontSize={10} fill="#ef4444" fontWeight="bold">
            {rising ? '↑' : '↓'}
          </text>
        </g>
      )
    }
    const color = personaMap[pid]?.avatar_color || '#888'
    return <circle key={`dot-${pid}-${seq}`} cx={cx} cy={cy} r={4} fill={color} stroke="#fff" strokeWidth={1} />
  }

  // Enhanced tooltip with turning point info
  const renderTooltip = ({ active, payload }: any) => {
    if (!active || !payload?.length) return null
    const items = payload.filter((p: any) => p.value != null && !String(p.dataKey).endsWith('_trend'))
    if (items.length === 0) return null
    return (
      <div className="emotion-tooltip">
        {items.map((item: any) => {
          const pid = item.dataKey as string
          const persona = personaMap[pid]
          const label = item.payload[`${pid}_label`] || ''
          const summary = item.payload[`${pid}_summary`] || ''
          const seq = item.payload.index
          const tp = turningPoints.find((t) => t.personaId === pid && t.index === seq)
          return (
            <div key={pid} style={{ marginBottom: 4 }}>
              <span style={{ color: item.stroke, fontWeight: 600 }}>
                {persona?.name || pid}
              </span>
              <span style={{ marginLeft: 8 }}>
                {item.value > 0 ? '+' : ''}{item.value}
              </span>
              {label && <span style={{ marginLeft: 6, color: '#888', fontSize: 12 }}>{label}</span>}
              {tp && (
                <div className="emotion-tp-badge">
                  转折点: {tp.prevScore > 0 ? '+' : ''}{tp.prevScore} → {tp.score > 0 ? '+' : ''}{tp.score}
                </div>
              )}
              {summary && <div style={{ color: '#aaa', fontSize: 11, marginTop: 2 }}>{summary}…</div>}
            </div>
          )
        })}
      </div>
    )
  }

  return (
    <div className="dialog-overlay" onClick={onClose}>
      <div className="dialog emotion-dialog" onClick={(e) => e.stopPropagation()}>
        <h3>角色情绪分析</h3>

        {/* Tab bar */}
        <div className="emotion-tabs">
          <button className={`emotion-tab ${tab === 'curve' ? 'active' : ''}`} onClick={() => setTab('curve')}>
            曲线图
          </button>
          <button className={`emotion-tab ${tab === 'heatmap' ? 'active' : ''}`} onClick={() => setTab('heatmap')}>
            热力图
          </button>
        </div>

        {data.length === 0 ? (
          <div className="emotion-empty">暂无情绪数据，发送新消息后将自动生成</div>
        ) : tab === 'curve' ? (
          <>
            <div className="emotion-chart-wrapper">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={data} margin={{ top: 10, right: 20, bottom: 10, left: 10 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                  <XAxis
                    dataKey="index"
                    label={{ value: '消息序号', position: 'insideBottom', offset: -5, fontSize: 12 }}
                    tick={{ fontSize: 12 }}
                  />
                  <YAxis domain={[-5, 5]} ticks={[-5, -3, -1, 0, 1, 3, 5]} tick={{ fontSize: 12 }} width={30} />
                  <ReferenceLine y={0} stroke="#d1d5db" strokeDasharray="3 3" />
                  <Tooltip content={renderTooltip} />
                  {/* Actual emotion lines */}
                  {personaIds.map((pid) => (
                    <Line
                      key={pid}
                      type="monotone"
                      dataKey={pid}
                      stroke={personaMap[pid]?.avatar_color || '#888'}
                      strokeWidth={2}
                      dot={renderDot(pid)}
                      activeDot={{ r: 6 }}
                      connectNulls
                    />
                  ))}
                  {/* Trend lines (dashed) */}
                  {trendData.length > 0 &&
                    personaIds.map((pid) => {
                      const hasTrend = trendData.some((d) => d[`${pid}_trend`] != null)
                      if (!hasTrend) return null
                      return (
                        <Line
                          key={`${pid}_trend`}
                          type="linear"
                          dataKey={`${pid}_trend`}
                          data={trendData}
                          stroke={personaMap[pid]?.avatar_color || '#888'}
                          strokeWidth={1.5}
                          strokeDasharray="6 4"
                          dot={false}
                          activeDot={false}
                          connectNulls
                          legendType="none"
                        />
                      )
                    })}
                </LineChart>
              </ResponsiveContainer>
            </div>
            {/* Turning points summary */}
            {turningPoints.length > 0 && (
              <div className="emotion-tp-summary">
                <strong>情绪转折点：</strong>
                {turningPoints.map((tp, i) => {
                  const name = personaMap[tp.personaId]?.name || tp.personaId
                  const dir = tp.score > tp.prevScore ? '↑' : '↓'
                  return (
                    <span key={i} className="emotion-tp-chip">
                      {name} #{tp.index} {dir} {tp.prevScore > 0 ? '+' : ''}{tp.prevScore}→{tp.score > 0 ? '+' : ''}{tp.score}
                    </span>
                  )
                })}
              </div>
            )}
            <div className="emotion-legend">
              {personaIds.map((pid) => (
                <div key={pid} className="emotion-legend-item">
                  <span className="emotion-legend-dot" style={{ background: personaMap[pid]?.avatar_color || '#888' }} />
                  {personaMap[pid]?.name || pid}
                </div>
              ))}
              <div className="emotion-legend-item">
                <span className="emotion-legend-line" /> 趋势线
              </div>
            </div>
          </>
        ) : (
          /* Heatmap Tab */
          <div className="emotion-heatmap">
            {/* Column headers */}
            <div className="heatmap-row heatmap-header">
              <div className="heatmap-label" />
              {Array.from({ length: maxIndex }, (_, i) => (
                <div key={i} className="heatmap-col-header">{i + 1}</div>
              ))}
            </div>
            {/* Data rows */}
            {heatmapRows.map((row) => (
              <div key={row.personaId} className="heatmap-row">
                <div className="heatmap-label" style={{ color: personaMap[row.personaId]?.avatar_color || '#888' }}>
                  {personaMap[row.personaId]?.name || row.personaId}
                </div>
                {row.cells.map((cell) => (
                  <div
                    key={cell.index}
                    className={`heatmap-cell ${cell.score == null ? 'empty' : ''}`}
                    style={{ backgroundColor: scoreToColor(cell.score) }}
                    onMouseEnter={() => setHoverCell(cell)}
                    onMouseLeave={() => setHoverCell(null)}
                  >
                    {cell.score != null && <span className="heatmap-score">{cell.score}</span>}
                  </div>
                ))}
              </div>
            ))}
            {/* Hover tooltip */}
            {hoverCell && hoverCell.score != null && (
              <div className="heatmap-tooltip">
                <strong style={{ color: personaMap[hoverCell.personaId]?.avatar_color || undefined }}>
                  {personaMap[hoverCell.personaId]?.name || hoverCell.personaId}
                </strong>
                {' '}#{hoverCell.index}: {hoverCell.score > 0 ? '+' : ''}{hoverCell.score}
                {hoverCell.label && <span> ({hoverCell.label})</span>}
              </div>
            )}
            {/* Color legend */}
            <div className="heatmap-color-legend">
              <span className="heatmap-legend-label">-5 反对</span>
              <div className="heatmap-gradient" />
              <span className="heatmap-legend-label">+5 支持</span>
            </div>
          </div>
        )}

        <div className="dialog-actions">
          <button className="btn-cancel" onClick={onClose}>关闭</button>
        </div>
      </div>
    </div>
  )
}
