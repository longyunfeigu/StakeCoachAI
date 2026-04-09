// input: messages (Message[]), personaMap (Record<string, PersonaSummary>)
// output: EmotionSidebar 实时情绪折线图侧边栏组件
// owner: wanhua.gu
// pos: 前端组件 - 对话界面旁的实时情绪可视化面板；一旦我被更新，务必更新我的开头注释以及所属文件夹的md

import { useMemo } from 'react'
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
import { X, Maximize2 } from 'lucide-react'
import type { Message, PersonaSummary } from '../services/api'
import './EmotionSidebar.css'

interface Props {
  messages: Message[]
  personaMap: Record<string, PersonaSummary>
  onClose: () => void
  onExpand: () => void
}

interface DataPoint {
  index: number
  label: string
  [personaId: string]: number | string | null
}

export default function EmotionSidebar({ messages, personaMap, onClose, onExpand }: Props) {
  const { data, personaIds, latestScores } = useMemo(() => {
    const personaMsgs = messages.filter(
      (m) => m.sender_type === 'persona' && m.emotion_score != null,
    )
    if (personaMsgs.length === 0)
      return { data: [] as DataPoint[], personaIds: [] as string[], latestScores: {} as Record<string, { score: number; label: string | null; delta: number | null }> }

    const ids = new Set<string>()
    const points: DataPoint[] = []
    // Track per-persona latest and previous scores
    const perPersonaLast: Record<string, { score: number; prev: number | null; label: string | null }> = {}

    let seq = 0
    for (const msg of personaMsgs) {
      ids.add(msg.sender_id)
      seq++
      const pt: DataPoint = { index: seq, label: `#${seq}` }
      pt[msg.sender_id] = msg.emotion_score
      pt[`${msg.sender_id}_label`] = msg.emotion_label
      points.push(pt)

      const prev = perPersonaLast[msg.sender_id]?.score ?? null
      perPersonaLast[msg.sender_id] = {
        score: msg.emotion_score!,
        prev,
        label: msg.emotion_label,
      }
    }

    const pids = Array.from(ids)
    const latest: Record<string, { score: number; label: string | null; delta: number | null }> = {}
    for (const pid of pids) {
      const info = perPersonaLast[pid]
      if (info) {
        latest[pid] = {
          score: info.score,
          label: info.label,
          delta: info.prev != null ? info.score - info.prev : null,
        }
      }
    }

    return { data: points, personaIds: pids, latestScores: latest }
  }, [messages])

  const renderTooltip = ({ active, payload }: any) => {
    if (!active || !payload?.length) return null
    const items = payload.filter((p: any) => p.value != null)
    if (items.length === 0) return null
    return (
      <div className="es-tooltip">
        {items.map((item: any) => {
          const pid = item.dataKey as string
          const persona = personaMap[pid]
          const label = item.payload[`${pid}_label`] || ''
          return (
            <div key={pid} className="es-tooltip-row">
              <span className="es-tooltip-dot" style={{ background: item.stroke }} />
              <span className="es-tooltip-name">{persona?.name || pid}</span>
              <span className="es-tooltip-score">
                {item.value > 0 ? '+' : ''}{item.value}
              </span>
              {label && <span className="es-tooltip-label">{label}</span>}
            </div>
          )
        })}
      </div>
    )
  }

  return (
    <aside className="emotion-sidebar">
      <div className="es-header">
        <h4>实时情绪</h4>
        <div className="es-header-actions">
          <button className="es-icon-btn" onClick={onExpand} title="详细分析">
            <Maximize2 size={14} />
          </button>
          <button className="es-icon-btn" onClick={onClose} title="关闭">
            <X size={14} />
          </button>
        </div>
      </div>

      {data.length === 0 ? (
        <div className="es-empty">发送消息后，情绪曲线将在此实时显示</div>
      ) : (
        <>
          <div className="es-chart">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={data} margin={{ top: 5, right: 12, bottom: 5, left: -10 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                <XAxis
                  dataKey="label"
                  tick={{ fontSize: 10 }}
                  interval="preserveStartEnd"
                />
                <YAxis
                  domain={[-5, 5]}
                  ticks={[-5, 0, 5]}
                  tick={{ fontSize: 10 }}
                  width={28}
                />
                <ReferenceLine y={0} stroke="var(--border)" strokeDasharray="3 3" />
                <Tooltip content={renderTooltip} />
                {personaIds.map((pid) => (
                  <Line
                    key={pid}
                    type="monotone"
                    dataKey={pid}
                    stroke={personaMap[pid]?.avatar_color || '#888'}
                    strokeWidth={2}
                    dot={{ r: 3, fill: personaMap[pid]?.avatar_color || '#888' }}
                    activeDot={{ r: 5 }}
                    connectNulls
                    isAnimationActive={false}
                  />
                ))}
              </LineChart>
            </ResponsiveContainer>
          </div>

          {/* Current emotion status for each persona */}
          <div className="es-status-list">
            {personaIds.map((pid) => {
              const info = latestScores[pid]
              if (!info) return null
              const persona = personaMap[pid]
              const deltaStr = info.delta != null
                ? `${info.delta > 0 ? '+' : ''}${info.delta}`
                : null
              const deltaClass = info.delta != null
                ? info.delta > 0 ? 'up' : info.delta < 0 ? 'down' : ''
                : ''
              return (
                <div key={pid} className="es-status-item">
                  <span
                    className="es-status-dot"
                    style={{ background: persona?.avatar_color || '#888' }}
                  />
                  <span className="es-status-name">{persona?.name || pid}</span>
                  <span className="es-status-score">
                    {info.score > 0 ? '+' : ''}{info.score}
                  </span>
                  {deltaStr && (
                    <span className={`es-status-delta ${deltaClass}`}>
                      ({deltaStr})
                    </span>
                  )}
                  {info.label && (
                    <span className="es-status-label">{info.label}</span>
                  )}
                </div>
              )
            })}
          </div>
        </>
      )}

      {/* Legend */}
      <div className="es-legend">
        {personaIds.map((pid) => (
          <div key={pid} className="es-legend-item">
            <span
              className="es-legend-dot"
              style={{ background: personaMap[pid]?.avatar_color || '#888' }}
            />
            <span>{personaMap[pid]?.name || pid}</span>
          </div>
        ))}
      </div>
    </aside>
  )
}
