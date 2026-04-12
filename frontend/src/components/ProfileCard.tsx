import React from 'react'
import { type ProfileCard as ProfileCardData } from '../services/api'
import './ProfileCard.css'

const DIMENSION_LABELS: Record<string, string> = {
  persuasion: '说服力',
  emotional_management: '情绪管理',
  active_listening: '倾听回应',
  structured_expression: '结构表达',
  conflict_resolution: '冲突处理',
  stakeholder_alignment: '利益对齐',
}

const DIMENSIONS = Object.keys(DIMENSION_LABELS)

interface Props {
  data: ProfileCardData
  cardRef?: React.RefObject<HTMLDivElement | null>
}

function getBarStyle(score: number): React.CSSProperties {
  const widthPct = `${(score / 5) * 100}%`
  if (score >= 3.5) {
    return {
      width: widthPct,
      background: 'linear-gradient(90deg, #4f46e5, #7c3aed)',
    }
  }
  return {
    width: widthPct,
    background: 'linear-gradient(90deg, #f59e0b, #ef4444)',
  }
}

export default function ProfileCard({ data, cardRef }: Props) {
  // If style_label is empty, the user has insufficient evaluations
  if (!data.style_label) {
    return (
      <div className="profile-card" ref={cardRef}>
        <div className="pc-placeholder">
          暂无足够数据生成沟通力名片，
          <br />
          请完成更多对话评估后再试。
        </div>
      </div>
    )
  }

  return (
    <div className="profile-card" ref={cardRef}>
      {/* Header */}
      <div className="profile-card-header">
        <div className="profile-card-logo">D</div>
        <div className="profile-card-header-text">
          <span className="profile-card-label">DABOSS PROFILE</span>
          <span className="profile-card-title">{data.style_label}</span>
        </div>
      </div>

      {/* Tags row */}
      {data.tags && data.tags.length > 0 && (
        <div className="profile-card-tags">
          {data.tags.map((tag, i) => (
            <span key={i} className={`profile-tag ${tag.type}`}>
              {tag.text}
            </span>
          ))}
        </div>
      )}

      {/* 6 progress bars */}
      <div className="profile-bars">
        {DIMENSIONS.map((dim) => {
          const score = data.scores?.[dim] ?? 0
          return (
            <div key={dim} className="profile-bar-row">
              <span className="profile-bar-label">{DIMENSION_LABELS[dim]}</span>
              <div className="profile-bar-track">
                {/* Use inline style for width and gradient — needed for html2canvas */}
                <div className="profile-bar-fill" style={getBarStyle(score)} />
              </div>
              <span className="profile-bar-score">{score.toFixed(1)}</span>
            </div>
          )
        })}
      </div>

      {/* Summary quote */}
      {data.summary && (
        <div className="profile-card-summary">{data.summary}</div>
      )}

      {/* Footer */}
      <div className="profile-card-footer">DaBoss · 测测你的职场沟通风格 →</div>
    </div>
  )
}
