import {
  RadarChart,
  Radar,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  ResponsiveContainer,
  Tooltip,
} from 'recharts'
import type { DefenseReport as DefenseReportData } from '../../services/api'
import './DefenseReport.css'

interface Props {
  report: DefenseReportData
}

interface RadarDataPoint {
  dimension: string
  score: number
}

function buildRadarData(dimensionScores: Record<string, number>): RadarDataPoint[] {
  return Object.entries(dimensionScores).map(([dim, score]) => ({
    dimension: dim,
    score,
  }))
}

function scoreClass(score: number): string {
  if (score >= 80) return 'high'
  if (score >= 60) return 'mid'
  return 'low'
}

function scoreBadgeClass(score: number): string {
  if (score >= 80) return 'dr-review-score-badge--high'
  if (score >= 60) return 'dr-review-score-badge--mid'
  return 'dr-review-score-badge--low'
}

export default function DefenseReport({ report }: Props) {
  const radarData = buildRadarData(report.dimension_scores)

  return (
    <div className="dr-container">
      {/* Overall score hero */}
      <div className="dr-score-hero">
        <span className={`dr-score-number dr-score-number--${scoreClass(report.overall_score)}`}>
          {report.overall_score}
        </span>
        <span className="dr-score-label">综合得分</span>
      </div>

      {/* Radar chart */}
      {radarData.length > 0 && (
        <div className="dr-radar-section">
          <h3 className="dr-section-title">维度评分</h3>
          <div className="dr-radar-wrapper">
            <ResponsiveContainer width="100%" height="100%">
              <RadarChart data={radarData} cx="50%" cy="50%" outerRadius="75%">
                <PolarGrid stroke="var(--border)" />
                <PolarAngleAxis
                  dataKey="dimension"
                  tick={{ fill: 'var(--text-secondary)', fontSize: 12 }}
                />
                <PolarRadiusAxis
                  angle={30}
                  domain={[0, 100]}
                  tick={{ fill: 'var(--text-muted)', fontSize: 10 }}
                />
                <Radar
                  name="得分"
                  dataKey="score"
                  stroke="var(--violet)"
                  fill="var(--violet)"
                  fillOpacity={0.25}
                  strokeWidth={2}
                />
                <Tooltip />
              </RadarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* Summary */}
      <div className="dr-summary-section">
        <h3 className="dr-section-title">综合评价</h3>
        <p className="dr-summary-text">{report.summary}</p>
      </div>

      {/* Top improvements */}
      {report.top_improvements.length > 0 && (
        <div className="dr-improvements-section">
          <h3 className="dr-section-title">重点改进方向</h3>
          <ul className="dr-improvements-list">
            {report.top_improvements.map((item, i) => (
              <li key={i} className="dr-improvement-item">
                <span className="dr-improvement-bullet">{i + 1}</span>
                <span>{item}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Question reviews */}
      {report.question_reviews.length > 0 && (
        <div className="dr-reviews-section">
          <h3 className="dr-section-title">逐题点评</h3>
          <div className="dr-review-list">
            {report.question_reviews.map((review, i) => (
              <div key={i} className="dr-review-card">
                <div className="dr-review-header">
                  <span className="dr-review-question">
                    {i + 1}. {review.question}
                  </span>
                  <span className={`dr-review-score-badge ${scoreBadgeClass(review.score)}`}>
                    {review.score}
                  </span>
                </div>
                <div className="dr-review-answer">
                  <span className="dr-review-answer-label">回答摘要:</span>
                  {review.user_answer_summary}
                </div>
                <div className="dr-review-feedback">
                  <span className="dr-review-feedback-label">点评:</span>
                  {review.feedback}
                </div>
                <div className="dr-review-improvement">
                  <span className="dr-review-improvement-label">改进建议:</span>
                  {review.improvement}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
