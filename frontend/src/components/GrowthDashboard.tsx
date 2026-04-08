import { useEffect, useState } from 'react'
import {
  RadarChart,
  Radar,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  ResponsiveContainer,
  Tooltip,
} from 'recharts'
import Markdown from 'react-markdown'
import { Sparkles, Loader2 } from 'lucide-react'
import {
  fetchGrowthDashboard,
  generateGrowthInsight,
  type GrowthDashboard as GrowthDashboardData,
} from '../services/api'
import './GrowthDashboard.css'

const DIMENSION_LABELS: Record<string, string> = {
  persuasion: '说服力',
  emotional_management: '情绪管理',
  active_listening: '倾听回应',
  structured_expression: '结构化表达',
  conflict_resolution: '冲突处理',
  stakeholder_alignment: '利益对齐',
}

const DIMENSIONS = Object.keys(DIMENSION_LABELS)

interface RadarDataPoint {
  dimension: string
  latest: number
  average: number
}

function buildRadarData(dashboard: GrowthDashboardData): RadarDataPoint[] {
  const evals = dashboard.evaluations
  return DIMENSIONS.map((dim) => {
    const latest = evals.length > 0 ? (evals[0].scores[dim]?.score ?? 0) : 0
    const allScores = evals.map((ev) => ev.scores[dim]?.score ?? 0).filter((s) => s > 0)
    const average = allScores.length > 0 ? Math.round((allScores.reduce((a, b) => a + b, 0) / allScores.length) * 10) / 10 : 0
    return { dimension: DIMENSION_LABELS[dim], latest, average }
  })
}

function scoreColor(score: number): string {
  if (score >= 4) return '#16a34a'
  if (score >= 3) return '#d97706'
  return '#dc2626'
}

interface Props {
  onCreateRoom: () => void
}

export default function GrowthDashboard({ onCreateRoom }: Props) {
  const [data, setData] = useState<GrowthDashboardData | null>(null)
  const [loading, setLoading] = useState(true)
  const [insight, setInsight] = useState<string | null>(null)
  const [insightLoading, setInsightLoading] = useState(false)

  useEffect(() => {
    setLoading(true)
    fetchGrowthDashboard()
      .then(setData)
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [])

  const handleGenerateInsight = async () => {
    setInsightLoading(true)
    try {
      const text = await generateGrowthInsight()
      setInsight(text)
    } catch (e) {
      console.error(e)
    } finally {
      setInsightLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="growth-dashboard">
        <div className="growth-loading">
          <Loader2 size={24} className="spin" />
          <span>加载成长数据...</span>
        </div>
      </div>
    )
  }

  if (!data || data.overview.total_evaluations === 0) {
    return (
      <div className="growth-dashboard">
        <div className="growth-empty">
          <div className="growth-empty-icon">
            <Sparkles size={48} strokeWidth={1.5} />
          </div>
          <h2>还没有能力评估数据</h2>
          <p>在聊天室中与 AI 角色对话，然后点击"分析"按钮生成能力评估。<br />完成 2 次以上评估后，就能看到成长趋势。</p>
          <button className="growth-cta" onClick={onCreateRoom}>
            开始一场练习
          </button>
        </div>
      </div>
    )
  }

  const radarData = buildRadarData(data)
  const { overview, evaluations } = data

  return (
    <div className="growth-dashboard">
      <h2 className="growth-title">成长轨迹</h2>

      {/* Stats cards */}
      <div className="growth-stats">
        <div className="stat-card">
          <div className="stat-value">{overview.total_sessions}</div>
          <div className="stat-label">练习次数</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">{overview.total_evaluations}</div>
          <div className="stat-label">评估次数</div>
        </div>
        <div className="stat-card">
          <div className="stat-value" style={{ color: scoreColor(overview.avg_overall_score) }}>
            {overview.avg_overall_score.toFixed(1)}
          </div>
          <div className="stat-label">平均分</div>
        </div>
        <div className="stat-card">
          <div className="stat-value" style={{ color: scoreColor(overview.latest_score) }}>
            {overview.latest_score.toFixed(1)}
          </div>
          <div className="stat-label">最新分</div>
        </div>
      </div>

      {/* Radar chart */}
      <div className="growth-radar-section">
        <h3>能力雷达图</h3>
        <div className="growth-radar-wrapper">
          <ResponsiveContainer width="100%" height={320}>
            <RadarChart data={radarData} cx="50%" cy="50%" outerRadius="75%">
              <PolarGrid stroke="#e5e7eb" />
              <PolarAngleAxis dataKey="dimension" tick={{ fontSize: 12, fill: '#6b7280' }} />
              <PolarRadiusAxis angle={90} domain={[0, 5]} tick={{ fontSize: 10 }} tickCount={6} />
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
                stroke="#2D9C6F"
                fill="#2D9C6F"
                fillOpacity={0.25}
                strokeWidth={2}
              />
            </RadarChart>
          </ResponsiveContainer>
          <div className="radar-legend">
            <span className="radar-legend-item">
              <span className="radar-dot" style={{ background: '#2D9C6F' }} /> 最新评估
            </span>
            {evaluations.length > 1 && (
              <span className="radar-legend-item">
                <span className="radar-dot dashed" /> 历史平均
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Dimension trends as table */}
      {evaluations.length > 1 && (
        <div className="dimension-trends">
          <h3>各维度趋势对比</h3>
          <div className="trends-table-wrap">
            <table className="trends-table">
              <thead>
                <tr>
                  <th>维度</th>
                  {evaluations.map((ev, i) => (
                    <th key={ev.id}>
                      <div className="trends-th-room">{ev.room_name || `#${i + 1}`}</div>
                      <div className="trends-th-date">
                        {ev.created_at ? new Date(ev.created_at).toLocaleDateString() : ''}
                      </div>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {DIMENSIONS.map((dim) => (
                  <tr key={dim}>
                    <td className="trends-dim-name">{DIMENSION_LABELS[dim]}</td>
                    {evaluations.map((ev) => {
                      const sc = ev.scores[dim]?.score ?? 0
                      return (
                        <td key={ev.id} className="trends-score-cell">
                          <span className="trends-score-badge" style={{ background: scoreColor(sc) + '20', color: scoreColor(sc) }}>
                            {sc}
                          </span>
                        </td>
                      )
                    })}
                  </tr>
                ))}
                <tr className="trends-total-row">
                  <td className="trends-dim-name">总分</td>
                  {evaluations.map((ev) => (
                    <td key={ev.id} className="trends-score-cell">
                      <strong style={{ color: scoreColor(ev.overall_score) }}>
                        {ev.overall_score.toFixed(1)}
                      </strong>
                    </td>
                  ))}
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Latest evaluation detail */}
      {evaluations.length > 0 && (
        <div className="growth-detail">
          <h3>最新评估详情</h3>
          <div className="detail-meta">
            {evaluations[0].room_name} &middot; 总分 {evaluations[0].overall_score.toFixed(1)}/5
          </div>
          {DIMENSIONS.map((dim) => {
            const sc = evaluations[0].scores[dim]
            if (!sc) return null
            return (
              <div key={dim} className="detail-item">
                <div className="detail-dim-header">
                  <span className="detail-dim-name">{DIMENSION_LABELS[dim]}</span>
                  <span className="detail-dim-score" style={{ color: scoreColor(sc.score) }}>
                    {sc.score}/5
                  </span>
                </div>
                {sc.evidence && <div className="detail-evidence">{sc.evidence}</div>}
                {sc.suggestion && <div className="detail-suggestion">{sc.suggestion}</div>}
              </div>
            )
          })}
        </div>
      )}

      {/* Growth insight */}
      <div className="growth-insight-section">
        <div className="insight-header">
          <h3>成长洞察</h3>
          <button
            className="insight-btn"
            onClick={handleGenerateInsight}
            disabled={insightLoading}
          >
            {insightLoading ? <Loader2 size={14} className="spin" /> : <Sparkles size={14} />}
            {insightLoading ? '生成中...' : '生成洞察'}
          </button>
        </div>
        {insightLoading && (
          <div className="insight-loading">
            <Loader2 size={20} className="spin" />
            <span>AI 正在分析你的成长轨迹...</span>
          </div>
        )}
        {insight && !insightLoading && (
          <div className="growth-insight-content">
            <Markdown>{insight}</Markdown>
          </div>
        )}
      </div>
    </div>
  )
}
