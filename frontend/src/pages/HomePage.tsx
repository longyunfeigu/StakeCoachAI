import React, { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import {
  Swords,
  MessageSquare,
  Activity,
  Users,
  Check,
  Lock,
  ChevronRight,
} from 'lucide-react'
import { useAppContext } from '../contexts/AppContext'
import { fetchRooms, type ChatRoom } from '../services/api'
import './HomePage.css'

/* ---------- helpers ---------- */

const AVATAR_COLORS = ['#8B5226', '#1E3A5F', '#3D2E5C', '#6B4226', '#2E4A3F', '#4A3060']

function getAvatarColor(id: string | number): string {
  const hash = String(id).split('').reduce((a, c) => a + c.charCodeAt(0), 0)
  return AVATAR_COLORS[hash % AVATAR_COLORS.length]
}

function getInitial(name: string): string {
  return name.charAt(0)
}

function timeAgo(dateStr: string | null): string {
  if (!dateStr) return ''
  const now = Date.now()
  const then = new Date(dateStr).getTime()
  if (isNaN(then)) return ''
  const diffMs = now - then
  const minutes = Math.floor(diffMs / 60000)
  if (minutes < 1) return '刚刚'
  if (minutes < 60) return `${minutes} 分钟前`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours} 小时前`
  const days = Math.floor(hours / 24)
  if (days === 1) return '昨天'
  if (days < 30) return `${days} 天前`
  return `${Math.floor(days / 30)} 个月前`
}

/* ---------- static data ---------- */

const dailyChallenge = {
  title: '向上汇报季度成果',
  progress: 0.35,
  xp: 100,
}

interface SkillNode {
  label: string
  status: 'done' | 'current' | 'locked'
}

const skillNodes: SkillNode[] = [
  { label: '入门对话', status: 'done' },
  { label: '情绪管理', status: 'done' },
  { label: '向上管理', status: 'current' },
  { label: '高层博弈', status: 'locked' },
  { label: '危机处理', status: 'locked' },
]

/* ---------- component ---------- */

const HomePage: React.FC = () => {
  const { personaMap, scenarios } = useAppContext()
  const [rooms, setRooms] = useState<ChatRoom[]>([])

  useEffect(() => {
    fetchRooms().then((data) => {
      // Sort by last_message_at descending, filter out battle_prep rooms
      const sorted = data
        .filter((r) => r.type !== 'battle_prep')
        .sort((a, b) => {
          const ta = a.last_message_at ? new Date(a.last_message_at).getTime() : 0
          const tb = b.last_message_at ? new Date(b.last_message_at).getTime() : 0
          return tb - ta
        })
      setRooms(sorted)
    }).catch(() => {})
  }, [])

  const recentRooms = rooms.slice(0, 3)
  const personaList = Object.values(personaMap)
  const personaCount = personaList.length
  const scenarioCount = scenarios?.length ?? 0
  return (
    <div className="home-page">
      {/* 1. Daily Challenge Banner */}
      <section className="home-daily-challenge">
        <div className="home-daily-challenge-accent" />
        <div className="home-daily-challenge-body">
          <div className="home-daily-challenge-top">
            <span className="home-section-label home-section-label--green">
              每日挑战
            </span>
            <span className="home-daily-xp">+{dailyChallenge.xp} XP</span>
          </div>
          <p className="home-daily-title">{dailyChallenge.title}</p>
          <div className="home-daily-progress-track">
            <div
              className="home-daily-progress-fill"
              style={{ width: `${dailyChallenge.progress * 100}%` }}
            />
          </div>
          <button className="home-daily-btn">开始挑战</button>
        </div>
      </section>

      {/* 2. Quick Action Cards */}
      <section className="home-actions-grid">
        {/* Battle Prep */}
        <Link to="/battle-prep" className="home-action-card home-action-card--amber">
          <div className="home-action-icon home-action-icon--amber">
            <Swords size={18} />
          </div>
          <div className="home-action-text">
            <span className="home-action-label home-action-label--amber">
              紧急备战
            </span>
            <span className="home-action-title">30 分钟快速演练</span>
            <span className="home-action-desc">
              针对即将到来的重要会议，进行高强度模拟对练
            </span>
          </div>
        </Link>

        {/* Free Practice */}
        <Link to="/chat" className="home-action-card home-action-card--green">
          <div className="home-action-icon home-action-icon--green">
            <MessageSquare size={18} />
          </div>
          <div className="home-action-text">
            <span className="home-action-label home-action-label--green">
              自由练习
            </span>
            <span className="home-action-title">开放式沟通模拟</span>
            <span className="home-action-desc">
              选择任意角色与场景，自由探索沟通策略
            </span>
          </div>
        </Link>

        {/* Growth */}
        <Link to="/growth" className="home-action-card home-action-card--violet">
          <div className="home-action-icon home-action-icon--violet">
            <Activity size={18} />
          </div>
          <div className="home-action-text">
            <span className="home-action-label home-action-label--violet">
              我的成长
            </span>
            <span className="home-action-title">沟通力评分</span>
            <span className="home-action-desc">
              追踪你的沟通能力成长轨迹
            </span>
          </div>
          <div className="home-action-score-block">
            <span className="home-action-score-number">82</span>
            <span className="home-action-score-trend">+5 本周</span>
          </div>
        </Link>

        {/* Persona Library */}
        <Link to="/settings" className="home-action-card home-action-card--neutral">
          <div className="home-action-icon home-action-icon--neutral">
            <Users size={18} />
          </div>
          <div className="home-action-text">
            <span className="home-action-label home-action-label--neutral">
              角色库
            </span>
            <span className="home-action-title">管理 AI 对手</span>
            <span className="home-action-desc">{personaCount} 个角色 &middot; {scenarioCount} 个场景</span>
          </div>
          <div className="home-action-avatars">
            {personaList.slice(0, 3).map((p, i) => (
              <span
                key={p.id || i}
                className="home-action-avatar-circle"
                style={{
                  backgroundColor: p.avatar_color || getAvatarColor(p.id || i),
                  zIndex: 3 - i,
                }}
              >
                {getInitial(p.name)}
              </span>
            ))}
            {personaCount > 3 && (
              <span className="home-action-avatar-more">+{personaCount - 3}</span>
            )}
          </div>
        </Link>
      </section>

      {/* 3. Recent Conversations */}
      <section className="home-recent">
        <div className="home-section-header">
          <span className="home-section-label">最近对话</span>
          <Link to="/chat" className="home-section-link">
            查看全部 <ChevronRight size={14} />
          </Link>
        </div>
        {recentRooms.length === 0 ? (
          <div className="home-recent-empty">
            <p>还没有对话记录</p>
            <Link to="/chat" className="home-recent-empty-cta">开始你的第一次练习</Link>
          </div>
        ) : (
          <div className="home-recent-row">
            {recentRooms.map((room) => {
              const firstPersonaId = room.persona_ids?.[0]
              const persona = firstPersonaId ? personaMap[firstPersonaId] : null
              const initial = persona ? getInitial(persona.name) : getInitial(room.name)
              const color = persona
                ? (persona.avatar_color || getAvatarColor(firstPersonaId))
                : getAvatarColor(room.id)
              return (
                <Link
                  key={room.id}
                  to={`/chat/${room.id}`}
                  className="home-recent-card"
                >
                  <span
                    className="home-recent-avatar"
                    style={{ backgroundColor: color }}
                  >
                    {initial}
                  </span>
                  <div className="home-recent-info">
                    <span className="home-recent-name">{room.name}</span>
                    <span className="home-recent-time">{timeAgo(room.last_message_at)}</span>
                  </div>
                </Link>
              )
            })}
          </div>
        )}
      </section>

      {/* 4. Skill Path Preview */}
      <section className="home-skill-path">
        <div className="home-section-header">
          <span className="home-section-label">技能路径</span>
          <Link to="/growth" className="home-section-link">
            展开 <ChevronRight size={14} />
          </Link>
        </div>
        <div className="home-skill-chain">
          {skillNodes.map((node, idx) => (
            <React.Fragment key={node.label}>
              {idx > 0 && <span className="home-skill-line" />}
              <div className={`home-skill-node home-skill-node--${node.status}`}>
                <span className="home-skill-circle">
                  {node.status === 'done' && <Check size={14} />}
                  {node.status === 'locked' && <Lock size={12} />}
                  {node.status === 'current' && (
                    <span className="home-skill-dot" />
                  )}
                </span>
                <span className="home-skill-label">{node.label}</span>
              </div>
            </React.Fragment>
          ))}
        </div>
      </section>
    </div>
  )
}

export default HomePage
