import React, { useState, useRef } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import {
  RadarChart,
  Radar,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  ResponsiveContainer,
  Tooltip,
} from 'recharts'
import html2canvas from 'html2canvas'
import {
  Loader2,
  Sparkles,
  Check,
  Lock,
  ChevronRight,
  ArrowUp,
  ArrowDown,
  Minus,
  Download,
  Share2,
  Flame,
  Star,
  Zap,
  Trophy,
} from 'lucide-react'
import { useGrowth, type SkillPathNode, type DimensionKey } from '../hooks/useGrowth'
import { generateProfileCard, type ProfileCard as ProfileCardData } from '../services/api'
import ProfileCard from '../components/ProfileCard'
import './GrowthPage.css'

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const DIMENSION_LABELS: Record<string, string> = {
  persuasion: '说服力',
  emotional_management: '情绪管理',
  active_listening: '倾听回应',
  structured_expression: '结构化表达',
  conflict_resolution: '冲突处理',
  stakeholder_alignment: '利益对齐',
}

const DIMENSIONS = Object.keys(DIMENSION_LABELS)

/** Map dimension keys to the 6 skill names from the task spec */
const SKILL_NAMES: Record<DimensionKey, string> = {
  persuasion: '入门对话',
  emotional_management: '情绪管理',
  active_listening: '向上管理',
  structured_expression: '高层博弈',
  conflict_resolution: '冲突处理',
  stakeholder_alignment: '共识达成',
}

const SKILL_DESCRIPTIONS: Record<DimensionKey, string> = {
  persuasion: '掌握基础沟通技巧，能够清晰表达观点并说服他人',
  emotional_management: '在高压场景中保持冷静，有效管理自身与对方情绪',
  active_listening: '与上级建立信任关系，高效汇报并争取资源支持',
  structured_expression: '在复杂利益格局中找到突破口，达成战略目标',
  conflict_resolution: '在分歧中寻找共识，化解冲突并维护关系',
  stakeholder_alignment: '协调多方利益诉求，推动达成共识性决策',
}

const SKILL_UNLOCK_CONDITIONS: Record<DimensionKey, string> = {
  persuasion: '完成 3 次对话评估且平均分 >= 3.0',
  emotional_management: '完成 3 次情绪管理评估且平均分 >= 3.0',
  active_listening: '完成 3 次倾听回应评估且平均分 >= 3.0',
  structured_expression: '完成 3 次结构化表达评估且平均分 >= 3.0',
  conflict_resolution: '完成 3 次冲突处理评估且平均分 >= 3.0',
  stakeholder_alignment: '完成 3 次利益对齐评估且平均分 >= 3.0',
}

const SKILL_SUGGESTIONS: Record<DimensionKey, string> = {
  persuasion: '尝试一场需要说服对方的模拟对话',
  emotional_management: '练习一场情绪波动较大的冲突场景',
  active_listening: '在下一场对话中专注展示向上汇报能力',
  structured_expression: '用金字塔原理结构化你的下一次发言',
  conflict_resolution: '模拟一场需要调解各方分歧的会议',
  stakeholder_alignment: '练习寻找多方利益交集的沟通策略',
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

interface RadarDataPoint {
  dimension: string
  latest: number
  average: number
}

function buildRadarData(
  evaluations: { scores: Record<string, { score: number }> }[],
): RadarDataPoint[] {
  return DIMENSIONS.map((dim) => {
    const latest = evaluations.length > 0 ? (evaluations[0].scores[dim]?.score ?? 0) : 0
    const allScores = evaluations.map((ev) => ev.scores[dim]?.score ?? 0).filter((s) => s > 0)
    const average =
      allScores.length > 0
        ? Math.round((allScores.reduce((a, b) => a + b, 0) / allScores.length) * 10) / 10
        : 0
    return { dimension: DIMENSION_LABELS[dim], latest, average }
  })
}

function scoreToGrade(score: number): string {
  if (score >= 4.7) return 'A+'
  if (score >= 4.3) return 'A'
  if (score >= 4.0) return 'A-'
  if (score >= 3.7) return 'B+'
  if (score >= 3.3) return 'B'
  if (score >= 3.0) return 'B-'
  if (score >= 2.7) return 'C+'
  if (score >= 2.3) return 'C'
  if (score >= 2.0) return 'C-'
  return 'D'
}

function gradeClass(score: number): string {
  if (score >= 3.5) return 'high'
  if (score >= 2.5) return 'mid'
  return 'low'
}

/** Compute week-over-week change per dimension. Compares latest vs second-latest eval. */
function computeDimensionChanges(
  evaluations: { scores: Record<string, { score: number }> }[],
): Record<string, number> {
  const changes: Record<string, number> = {}
  if (evaluations.length < 2) return changes
  for (const dim of DIMENSIONS) {
    const latest = evaluations[0].scores[dim]?.score ?? 0
    const previous = evaluations[1].scores[dim]?.score ?? 0
    changes[dim] = Math.round((latest - previous) * 10) / 10
  }
  return changes
}

/** Determine skill status from SkillPathNode data */
function getSkillStatus(
  node: SkillPathNode,
  index: number,
  allNodes: SkillPathNode[],
): 'completed' | 'current' | 'locked' {
  if (node.unlocked) return 'completed'
  // The first non-unlocked node after unlocked ones is "current"
  const allBefore = allNodes.slice(0, index)
  const anyUnlockedBefore = allBefore.length === 0 || allBefore.some((n) => n.unlocked)
  if (anyUnlockedBefore && !node.unlocked) {
    // Check if this is the first locked one
    const firstLockedIdx = allNodes.findIndex((n) => !n.unlocked)
    if (firstLockedIdx === index) return 'current'
  }
  return 'locked'
}

/** Build a short feedback summary from the evaluation's dimension scores */
function buildFeedbackSummary(scores: Record<string, { score: number; suggestion?: string }>): string {
  const entries = Object.entries(scores)
  // Find best and worst
  let best = entries[0]
  let worst = entries[0]
  for (const entry of entries) {
    if (entry[1].score > best[1].score) best = entry
    if (entry[1].score < worst[1].score) worst = entry
  }
  const bestLabel = DIMENSION_LABELS[best?.[0]] || best?.[0]
  const worstLabel = DIMENSION_LABELS[worst?.[0]] || worst?.[0]
  if (best && worst && best[0] !== worst[0]) {
    return `${bestLabel} 表现最佳 (${best[1].score})，${worstLabel} 有提升空间 (${worst[1].score})`
  }
  return worst?.[1]?.suggestion || ''
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

const GrowthPage: React.FC = () => {
  const navigate = useNavigate()
  const {
    dashboard,
    loading,
    error,
    xp,
    levelInfo,
    streak,
    skillPath,
  } = useGrowth()

  const [profileCard, setProfileCard] = useState<ProfileCardData | null>(null)
  const [profileCardLoading, setProfileCardLoading] = useState(false)
  const [downloading, setDownloading] = useState(false)
  const cardRef = useRef<HTMLDivElement>(null)

  const handleGenerateCard = async () => {
    setProfileCardLoading(true)
    try {
      const card = await generateProfileCard()
      setProfileCard(card)
    } catch (e) {
      console.error(e)
    } finally {
      setProfileCardLoading(false)
    }
  }

  const handleDownload = async () => {
    const el = cardRef.current
    if (!el) return
    setDownloading(true)
    try {
      const canvas = await html2canvas(el, { scale: 2, backgroundColor: '#fff' })
      const link = document.createElement('a')
      link.download = '沟通力名片.png'
      link.href = canvas.toDataURL('image/png')
      link.click()
    } finally {
      setDownloading(false)
    }
  }

  // Loading state
  if (loading) {
    return (
      <div className="growth-page">
        <div className="gp-loading">
          <Loader2 size={24} className="gp-spin" />
          <span>加载成长数据...</span>
        </div>
      </div>
    )
  }

  // Error state
  if (error) {
    return (
      <div className="growth-page">
        <div className="gp-empty">
          <p>加载失败: {error}</p>
        </div>
      </div>
    )
  }

  // Empty state
  if (!dashboard || dashboard.overview.total_evaluations === 0) {
    return (
      <div className="growth-page">
        <div className="gp-empty">
          <div className="gp-empty-icon">
            <Sparkles size={48} strokeWidth={1.5} />
          </div>
          <h2>还没有能力评估数据</h2>
          <p>
            在聊天室中与 AI 角色对话，然后点击"分析"按钮生成能力评估。
            <br />
            完成 2 次以上评估后，就能看到成长趋势。
          </p>
          <button className="gp-empty-btn" onClick={() => navigate('/chat')}>
            开始一场练习
          </button>
        </div>
      </div>
    )
  }

  const { evaluations, overview } = dashboard
  const radarData = buildRadarData(evaluations)
  const dimChanges = computeDimensionChanges(evaluations)

  return (
    <div className="growth-page">
      {/* Gamification stats row */}
      <div className="gp-gamification-row">
        <div className="gp-gam-card">
          <div className="gp-gam-value">{xp}</div>
          <div className="gp-gam-label">
            <Zap size={11} /> 总经验值
          </div>
        </div>
        <div className="gp-gam-card">
          <div className="gp-gam-value">Lv.{levelInfo.level}</div>
          <div className="gp-gam-label">
            <Trophy size={11} /> 等级
          </div>
          <div className="gp-level-bar">
            <div
              className="gp-level-bar-fill"
              style={{ width: `${levelInfo.progress * 100}%` }}
            />
          </div>
        </div>
        <div className="gp-gam-card">
          <div className="gp-gam-value">{streak}</div>
          <div className="gp-gam-label">
            <Flame size={11} /> 连续天数
          </div>
        </div>
        <div className="gp-gam-card">
          <div className="gp-gam-value">{overview.total_evaluations}</div>
          <div className="gp-gam-label">
            <Star size={11} /> 评估次数
          </div>
        </div>
      </div>

      {/* 1. Overall Score Header */}
      <section className="gp-score-header">
        <div className="gp-score-header-top">
          <span className="gp-section-label">能力总览</span>
        </div>

        <div className="gp-score-summary">
          <div className="gp-big-score">
            <span className="gp-big-score-value">
              {overview.latest_score.toFixed(1)}
            </span>
            <span className="gp-big-score-label">最新总分 / 5.0</span>
          </div>

          <div className="gp-radar-container">
            <ResponsiveContainer width="100%" height={280}>
              <RadarChart data={radarData} cx="50%" cy="50%" outerRadius="75%">
                <PolarGrid stroke="#e5e7eb" />
                <PolarAngleAxis
                  dataKey="dimension"
                  tick={{ fontSize: 12, fill: '#6b7280' }}
                />
                <PolarRadiusAxis
                  angle={90}
                  domain={[0, 5]}
                  tick={{ fontSize: 10 }}
                  tickCount={6}
                />
                <Tooltip />
                {evaluations.length > 1 && (
                  <Radar
                    name="历史平均"
                    dataKey="average"
                    stroke="#9ca3af"
                    fill="#9ca3af"
                    fillOpacity={0.15}
                    strokeDasharray="4 4"
                  />
                )}
                <Radar
                  name="最新评估"
                  dataKey="latest"
                  stroke="var(--violet, #8B7EC8)"
                  fill="var(--violet, #8B7EC8)"
                  fillOpacity={0.25}
                  strokeWidth={2}
                />
              </RadarChart>
            </ResponsiveContainer>
            <div className="gp-radar-legend">
              <span className="gp-radar-legend-item">
                <span className="gp-radar-dot" style={{ background: 'var(--violet, #8B7EC8)' }} /> 最新评估
              </span>
              {evaluations.length > 1 && (
                <span className="gp-radar-legend-item">
                  <span className="gp-radar-dot dashed" /> 历史平均
                </span>
              )}
            </div>
          </div>
        </div>

        {/* Week-over-week dimension changes */}
        {evaluations.length > 1 && Object.keys(dimChanges).length > 0 && (
          <div className="gp-dimension-changes">
            {DIMENSIONS.map((dim) => {
              const change = dimChanges[dim] ?? 0
              const arrow =
                change > 0 ? 'up' : change < 0 ? 'down' : 'same'
              return (
                <div key={dim} className="gp-dim-change">
                  <span className="gp-dim-change-name">
                    {DIMENSION_LABELS[dim]}
                  </span>
                  <span className={`gp-dim-change-arrow ${arrow}`}>
                    {arrow === 'up' && <><ArrowUp size={12} />+{change}</>}
                    {arrow === 'down' && <><ArrowDown size={12} />{change}</>}
                    {arrow === 'same' && <><Minus size={12} />0</>}
                  </span>
                </div>
              )
            })}
          </div>
        )}
      </section>

      {/* 2. Skill Path Detail (vertical timeline) */}
      <section className="gp-skill-path">
        <h3 className="gp-skill-path-title">技能路径</h3>
        <div className="gp-timeline">
          {skillPath.map((node, idx) => {
            const status = getSkillStatus(node, idx, skillPath)
            const dim = node.dimension
            return (
              <div
                key={dim}
                className={`gp-timeline-node gp-timeline-node--${status}`}
              >
                <div className="gp-timeline-circle">
                  {status === 'completed' && <Check size={14} />}
                  {status === 'current' && <span className="gp-timeline-circle-dot" />}
                  {status === 'locked' && <Lock size={12} />}
                </div>
                <div className="gp-timeline-name">{SKILL_NAMES[dim]}</div>
                <div className="gp-timeline-desc">
                  {SKILL_DESCRIPTIONS[dim]}
                </div>
                {status === 'completed' && (
                  <div className="gp-timeline-status-badge completed">
                    <Check size={11} /> 已完成 &middot; 平均 {node.averageScore}/5
                  </div>
                )}
                {status === 'current' && (
                  <div className="gp-timeline-suggestion">
                    <Sparkles size={12} /> 推荐练习: {SKILL_SUGGESTIONS[dim]}
                  </div>
                )}
                {status === 'locked' && (
                  <div className="gp-timeline-status-badge locked">
                    <Lock size={11} /> {SKILL_UNLOCK_CONDITIONS[dim]}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      </section>

      {/* 3. Evaluation History */}
      <section className="gp-eval-history">
        <h3 className="gp-eval-history-title">评估历史</h3>
        <div className="gp-eval-list">
          {evaluations.map((ev) => {
            const grade = scoreToGrade(ev.overall_score)
            const cls = gradeClass(ev.overall_score)
            const date = ev.created_at
              ? new Date(ev.created_at).toLocaleDateString('zh-CN')
              : ''
            const feedback = buildFeedbackSummary(ev.scores)
            return (
              <Link
                key={ev.id}
                to={`/chat/${ev.room_id}`}
                className="gp-eval-card"
              >
                <div className={`gp-eval-grade gp-eval-grade--${cls}`}>
                  {grade}
                </div>
                <div className="gp-eval-info">
                  <span className="gp-eval-name">
                    {ev.room_name || `评估 #${ev.id}`}
                  </span>
                  <span className="gp-eval-meta">
                    {date} &middot; 总分 {ev.overall_score.toFixed(1)}/5
                  </span>
                  {feedback && (
                    <span className="gp-eval-feedback">{feedback}</span>
                  )}
                </div>
                <ChevronRight size={16} className="gp-eval-arrow" />
              </Link>
            )
          })}
        </div>
      </section>

      {/* 4. Profile Card */}
      <section className="gp-profile-section">
        <div className="gp-profile-header">
          <h3 className="gp-profile-title">沟通力名片</h3>
          {profileCard && (
            <button
              className="gp-download-btn"
              onClick={handleDownload}
              disabled={downloading}
            >
              {downloading ? (
                <Loader2 size={14} className="gp-spin" />
              ) : (
                <Download size={14} />
              )}
              {downloading ? '生成中...' : '下载为图片'}
            </button>
          )}
        </div>

        {!profileCard ? (
          <div className="gp-profile-placeholder">
            <button
              className="gp-generate-card-btn"
              onClick={handleGenerateCard}
              disabled={profileCardLoading || overview.total_evaluations < 2}
              title={
                overview.total_evaluations < 2
                  ? `再完成 ${2 - overview.total_evaluations} 次练习即可解锁`
                  : '生成沟通力名片'
              }
            >
              {profileCardLoading ? (
                <Loader2 size={14} className="gp-spin" />
              ) : (
                <Share2 size={14} />
              )}
              {profileCardLoading ? '生成中...' : '生成我的名片'}
            </button>
          </div>
        ) : (
          <div className="gp-profile-card-wrapper">
            <ProfileCard data={profileCard} cardRef={cardRef} />
          </div>
        )}
      </section>
    </div>
  )
}

export default GrowthPage
