import { ChevronRight, ChevronLeft } from 'lucide-react'
import Avatar from '../Avatar'
import type { PersonaSummary } from '../../services/api'
import './ContextPanel.css'

export interface ContextPanelProps {
  /** Persona(s) in this room */
  personas: PersonaSummary[]
  /** Collapse state */
  collapsed: boolean
  onToggle: () => void
  /** Open emotion curve modal */
  onExpandEmotion?: () => void
}

/* Placeholder personality tags for personas (will be wired to real data later) */
const PLACEHOLDER_TAGS: Record<string, string[]> = {}

/** Map a tag string to a soft color. Deterministic based on tag text. */
function tagColor(tag: string): { bg: string; color: string } {
  const palette = [
    { bg: 'rgba(45,156,111,0.12)', color: '#1a7a52' },
    { bg: 'rgba(59,130,246,0.12)', color: '#2563eb' },
    { bg: 'rgba(139,92,246,0.12)', color: '#7c3aed' },
    { bg: 'rgba(245,158,11,0.12)', color: '#b45309' },
    { bg: 'rgba(239,68,68,0.10)', color: '#dc2626' },
  ]
  let hash = 0
  for (let i = 0; i < tag.length; i++) hash = (hash * 31 + tag.charCodeAt(i)) | 0
  return palette[Math.abs(hash) % palette.length]
}

/** Mini bar chart for emotion trend (placeholder data) */
function EmotionMiniChart() {
  const bars = [
    { value: 0.3, label: '平静' },
    { value: 0.6, label: '紧张' },
    { value: 0.4, label: '缓和' },
    { value: 0.8, label: '对抗' },
    { value: 0.5, label: '合作' },
  ]
  const intensityColor = (v: number) => {
    if (v > 0.7) return 'var(--rose)'
    if (v > 0.5) return 'var(--amber)'
    return 'var(--green, #2D9C6F)'
  }
  return (
    <div className="ctx-emotion-chart">
      {bars.map((b, i) => (
        <div key={i} className="ctx-emotion-bar-wrapper">
          <div
            className="ctx-emotion-bar"
            style={{ height: `${b.value * 40}px`, background: intensityColor(b.value) }}
          />
          <span className="ctx-emotion-bar-label">{b.label}</span>
        </div>
      ))}
    </div>
  )
}

export default function ContextPanel({
  personas,
  collapsed,
  onToggle,
  onExpandEmotion,
}: ContextPanelProps) {
  /* Placeholder score data -- will be replaced with real data later */
  const grade = 'B+'
  const metrics = [
    { label: '说服力', value: 72 },
    { label: '情绪管理', value: 85 },
    { label: '结构化', value: 68 },
    { label: '倾听', value: 78 },
  ]
  const sessionXP = 120

  return (
    <aside className={`context-panel${collapsed ? ' collapsed' : ''}`}>
      <button className="ctx-toggle" onClick={onToggle} title={collapsed ? '展开面板' : '收起面板'}>
        {collapsed ? <ChevronLeft size={14} /> : <ChevronRight size={14} />}
      </button>

      {!collapsed && (
        <div className="ctx-body">
          {/* Opponent profiles */}
          {personas.map((p) => {
            const tags = PLACEHOLDER_TAGS[p.id] || [p.role || '未知角色']
            return (
              <div key={p.id} className="ctx-profile-card">
                <div className="ctx-profile-header">
                  <Avatar name={p.name} color={p.avatar_color || '#2D9C6F'} size={32} />
                  <span className="ctx-profile-name">{p.name}</span>
                </div>
                <div className="ctx-profile-tags">
                  {tags.map((t) => {
                    const c = tagColor(t)
                    return (
                      <span key={t} className="ctx-tag" style={{ background: c.bg, color: c.color }}>
                        {t}
                      </span>
                    )
                  })}
                </div>
              </div>
            )
          })}

          {/* Emotion trend */}
          <div className="ctx-section">
            <div className="ctx-section-title">情绪趋势</div>
            <EmotionMiniChart />
            {onExpandEmotion && (
              <button className="ctx-link-btn" onClick={onExpandEmotion}>
                查看详情 →
              </button>
            )}
          </div>

          {/* Live score */}
          <div className="ctx-section">
            <div className="ctx-section-title">实时评分</div>
            <div className="ctx-score-area">
              <div className="ctx-grade">{grade}</div>
              <div className="ctx-metrics-grid">
                {metrics.map((m) => (
                  <div key={m.label} className="ctx-metric">
                    <span className="ctx-metric-value">{m.value}</span>
                    <span className="ctx-metric-label">{m.label}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Session XP */}
          <div className="ctx-xp-card">
            <span className="ctx-xp-label">本次经验</span>
            <span className="ctx-xp-value">+{sessionXP} XP</span>
          </div>
        </div>
      )}
    </aside>
  )
}
