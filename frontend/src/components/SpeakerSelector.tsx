import { Check, Users, MessageSquare, ChevronRight } from 'lucide-react'
import type { DetectedSpeaker } from '../services/api'
import './SpeakerSelector.css'

interface Props {
  speakers: DetectedSpeaker[]
  selected: Set<string>
  onToggle: (name: string) => void
  onConfirm: () => void
  onSkip: () => void
  disabled?: boolean
}

const DOMINANCE_BADGE: Record<string, { label: string; cls: string }> = {
  high: { label: '强势', cls: 'badge-high' },
  medium: { label: '中等', cls: 'badge-medium' },
  low: { label: '温和', cls: 'badge-low' },
}

export default function SpeakerSelector({
  speakers,
  selected,
  onToggle,
  onConfirm,
  onSkip,
  disabled,
}: Props) {
  return (
    <div className="speaker-selector">
      <div className="speaker-header">
        <Users size={18} />
        <h3>检测到 {speakers.length} 位说话人</h3>
      </div>
      <p className="speaker-hint">选择要生成对手画像的人（可多选）</p>

      <div className="speaker-list">
        {speakers.map((s) => {
          const isSelected = selected.has(s.name)
          const badge = DOMINANCE_BADGE[s.dominance_level] || DOMINANCE_BADGE.medium
          return (
            <button
              key={s.name}
              type="button"
              className={`speaker-card ${isSelected ? 'selected' : ''}`}
              onClick={() => onToggle(s.name)}
              disabled={disabled}
            >
              <div className="speaker-check">
                {isSelected && <Check size={14} />}
              </div>
              <div className="speaker-info">
                <div className="speaker-name-row">
                  <span className="speaker-name">{s.name}</span>
                  {s.role && <span className="speaker-role">{s.role}</span>}
                  <span className={`speaker-badge ${badge.cls}`}>{badge.label}</span>
                </div>
                <div className="speaker-meta">
                  <MessageSquare size={12} />
                  <span>{s.speaking_turns} 次发言</span>
                </div>
                {s.sample_quote && (
                  <div className="speaker-quote">"{s.sample_quote}"</div>
                )}
              </div>
            </button>
          )
        })}
      </div>

      <div className="speaker-actions">
        <button
          type="button"
          className="btn-primary speaker-confirm"
          onClick={onConfirm}
          disabled={disabled || selected.size === 0}
        >
          为选中的 {selected.size} 人生成画像
          <ChevronRight size={14} />
        </button>
        <button
          type="button"
          className="btn-ghost speaker-skip"
          onClick={onSkip}
          disabled={disabled}
        >
          跳过，直接分析全部素材
        </button>
      </div>
    </div>
  )
}
