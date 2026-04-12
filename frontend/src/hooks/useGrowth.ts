import { useEffect, useState, useMemo, useCallback } from 'react'
import {
  fetchGrowthDashboard,
  fetchRooms,
  type GrowthDashboard as GrowthDashboardData,
  type CompetencyEvaluation,
  type ChatRoom,
} from '../services/api'

// ---------------------------------------------------------------------------
// Grade-to-XP mapping
// ---------------------------------------------------------------------------

const GRADE_XP: Record<string, number> = {
  'A+': 100,
  A: 95,
  'A-': 90,
  'B+': 80,
  B: 75,
  'B-': 70,
  'C+': 65,
  C: 60,
  'C-': 55,
  D: 40,
}

/**
 * Compute total XP from evaluation overall scores.
 * The overall_score is on a 0-5 scale; we map it to letter grades then XP.
 */
export function computeXP(evaluations: CompetencyEvaluation[]): number {
  let total = 0
  for (const ev of evaluations) {
    const score = ev.overall_score
    const grade = scoreToGrade(score)
    total += GRADE_XP[grade] ?? 40
  }
  return total
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

// ---------------------------------------------------------------------------
// Level thresholds
// ---------------------------------------------------------------------------

const LEVEL_THRESHOLDS = [
  { level: 1, xp: 0 },
  { level: 2, xp: 200 },
  { level: 3, xp: 500 },
  { level: 4, xp: 1000 },
  { level: 5, xp: 2000 },
  { level: 6, xp: 3500 },
  { level: 7, xp: 5500 },
  { level: 8, xp: 8000 },
  { level: 9, xp: 11000 },
  { level: 10, xp: 15000 },
]

export interface LevelInfo {
  level: number
  currentXP: number
  nextLevelXP: number | null // null if max level
  progress: number // 0-1 fraction toward next level
}

export function computeLevel(xp: number): LevelInfo {
  let currentLevel = LEVEL_THRESHOLDS[0]
  for (const t of LEVEL_THRESHOLDS) {
    if (xp >= t.xp) {
      currentLevel = t
    } else {
      break
    }
  }
  const idx = LEVEL_THRESHOLDS.indexOf(currentLevel)
  const nextLevel = idx < LEVEL_THRESHOLDS.length - 1 ? LEVEL_THRESHOLDS[idx + 1] : null
  const progress = nextLevel
    ? (xp - currentLevel.xp) / (nextLevel.xp - currentLevel.xp)
    : 1
  return {
    level: currentLevel.level,
    currentXP: xp,
    nextLevelXP: nextLevel?.xp ?? null,
    progress: Math.min(1, Math.max(0, progress)),
  }
}

// ---------------------------------------------------------------------------
// Streak computation
// ---------------------------------------------------------------------------

/**
 * Count consecutive days (ending today or yesterday) that have at least one
 * completed room (a room with last_message_at).
 */
export function computeStreak(rooms: ChatRoom[]): number {
  if (rooms.length === 0) return 0

  // Collect unique dates that have activity
  const activeDates = new Set<string>()
  for (const room of rooms) {
    if (room.last_message_at) {
      const d = new Date(room.last_message_at)
      if (!isNaN(d.getTime())) {
        activeDates.add(d.toISOString().slice(0, 10))
      }
    }
  }

  if (activeDates.size === 0) return 0

  // Walk backwards from today
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  let streak = 0
  let checkDate = new Date(today)

  // If today has no activity, start from yesterday (still counts as active streak)
  const todayStr = checkDate.toISOString().slice(0, 10)
  if (!activeDates.has(todayStr)) {
    checkDate.setDate(checkDate.getDate() - 1)
    const yesterdayStr = checkDate.toISOString().slice(0, 10)
    if (!activeDates.has(yesterdayStr)) {
      return 0
    }
  }

  while (true) {
    const dateStr = checkDate.toISOString().slice(0, 10)
    if (activeDates.has(dateStr)) {
      streak++
      checkDate.setDate(checkDate.getDate() - 1)
    } else {
      break
    }
  }

  return streak
}

// ---------------------------------------------------------------------------
// Daily challenge
// ---------------------------------------------------------------------------

const DIMENSION_KEYS = [
  'persuasion',
  'emotional_management',
  'active_listening',
  'structured_expression',
  'conflict_resolution',
  'stakeholder_alignment',
] as const

export type DimensionKey = (typeof DIMENSION_KEYS)[number]

const DIMENSION_LABELS: Record<DimensionKey, string> = {
  persuasion: '说服力',
  emotional_management: '情绪管理',
  active_listening: '倾听回应',
  structured_expression: '结构化表达',
  conflict_resolution: '冲突处理',
  stakeholder_alignment: '利益对齐',
}

const CHALLENGE_SUGGESTIONS: Record<DimensionKey, string> = {
  persuasion: '尝试一场需要说服反对者的模拟对话',
  emotional_management: '练习一场情绪波动较大的冲突场景',
  active_listening: '在下一场对话中专注倾听并复述对方要点',
  structured_expression: '用金字塔原理结构化你的下一次发言',
  conflict_resolution: '模拟一场需要调解各方分歧的会议',
  stakeholder_alignment: '练习寻找多方利益交集的沟通策略',
}

export interface DailyChallenge {
  weakestDimension: DimensionKey
  dimensionLabel: string
  suggestion: string
}

/**
 * Pick the weakest dimension from average scores and suggest a scenario.
 */
export function computeDailyChallenge(
  dimensionTrends: Record<string, { date: string | null; score: number }[]>,
): DailyChallenge | null {
  let weakest: DimensionKey | null = null
  let lowestAvg = Infinity

  for (const dim of DIMENSION_KEYS) {
    const trend = dimensionTrends[dim]
    if (!trend || trend.length === 0) continue
    const avg = trend.reduce((sum, t) => sum + t.score, 0) / trend.length
    if (avg < lowestAvg) {
      lowestAvg = avg
      weakest = dim
    }
  }

  if (!weakest) return null

  return {
    weakestDimension: weakest,
    dimensionLabel: DIMENSION_LABELS[weakest],
    suggestion: CHALLENGE_SUGGESTIONS[weakest],
  }
}

// ---------------------------------------------------------------------------
// Skill path
// ---------------------------------------------------------------------------

export interface SkillPathNode {
  dimension: DimensionKey
  label: string
  unlocked: boolean
  averageScore: number
  evaluationCount: number
}

/**
 * Map 6 dimensions to skill path nodes.
 * A dimension is "unlocked" when the average score >= 60 (on a 0-100 scale)
 * across 3+ evaluations. The API scores are on a 0-5 scale, so we normalize:
 * unlocked = (avgScore / 5) * 100 >= 60, i.e. avgScore >= 3.0
 */
export function computeSkillPath(
  dimensionTrends: Record<string, { date: string | null; score: number }[]>,
  _evaluationCount?: number,
): SkillPathNode[] {
  return DIMENSION_KEYS.map((dim) => {
    const trend = dimensionTrends[dim] || []
    const avg = trend.length > 0
      ? trend.reduce((sum, t) => sum + t.score, 0) / trend.length
      : 0
    const dimEvalCount = trend.length
    // Unlocked: average score >= 3.0 (i.e., 60% on 0-100 scale) AND at least 3 evaluations
    const unlocked = dimEvalCount >= 3 && avg >= 3.0
    return {
      dimension: dim,
      label: DIMENSION_LABELS[dim],
      unlocked,
      averageScore: Math.round(avg * 10) / 10,
      evaluationCount: dimEvalCount,
    }
  })
}

// ---------------------------------------------------------------------------
// The hook
// ---------------------------------------------------------------------------

export interface UseGrowthReturn {
  dashboard: GrowthDashboardData | null
  loading: boolean
  error: string | null
  xp: number
  levelInfo: LevelInfo
  streak: number
  dailyChallenge: DailyChallenge | null
  skillPath: SkillPathNode[]
  reload: () => void
}

export function useGrowth(): UseGrowthReturn {
  const [dashboard, setDashboard] = useState<GrowthDashboardData | null>(null)
  const [rooms, setRooms] = useState<ChatRoom[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(() => {
    setLoading(true)
    setError(null)
    Promise.all([fetchGrowthDashboard(), fetchRooms()])
      .then(([dash, roomList]) => {
        setDashboard(dash)
        setRooms(roomList)
      })
      .catch((e) => {
        setError(e?.message || 'Failed to load growth data')
      })
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const xp = useMemo(
    () => (dashboard ? computeXP(dashboard.evaluations) : 0),
    [dashboard],
  )

  const levelInfo = useMemo(() => computeLevel(xp), [xp])

  const streak = useMemo(() => computeStreak(rooms), [rooms])

  const dailyChallenge = useMemo(
    () => (dashboard ? computeDailyChallenge(dashboard.dimension_trends) : null),
    [dashboard],
  )

  const skillPath = useMemo(
    () =>
      dashboard
        ? computeSkillPath(
            dashboard.dimension_trends,
            dashboard.overview.total_evaluations,
          )
        : [],
    [dashboard],
  )

  return {
    dashboard,
    loading,
    error,
    xp,
    levelInfo,
    streak,
    dailyChallenge,
    skillPath,
    reload: load,
  }
}
