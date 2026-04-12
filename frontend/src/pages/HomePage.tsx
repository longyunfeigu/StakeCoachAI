import React from 'react'
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
import './HomePage.css'

/* ---------- hardcoded placeholder data ---------- */

const dailyChallenge = {
  title: '向上汇报季度成果',
  progress: 0.35,
  xp: 100,
}

const recentConversations = [
  {
    id: 1,
    name: '张总监 1:1',
    surname: '张',
    color: '#8B5226',
    timeAgo: '2 小时前',
    grade: 'A',
  },
  {
    id: 2,
    name: '李经理项目评审',
    surname: '李',
    color: '#1E3A5F',
    timeAgo: '昨天',
    grade: 'B+',
  },
  {
    id: 3,
    name: '王副总沟通',
    surname: '王',
    color: '#3D2E5C',
    timeAgo: '3 天前',
    grade: 'A-',
  },
]

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

const personaAvatars = [
  { surname: '张', color: '#D4A574' },
  { surname: '李', color: '#6BA3D6' },
  { surname: '王', color: '#A88EC8' },
]

/* ---------- component ---------- */

const HomePage: React.FC = () => {
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
            <span className="home-action-desc">6 个角色 &middot; 3 个场景</span>
          </div>
          <div className="home-action-avatars">
            {personaAvatars.map((a, i) => (
              <span
                key={i}
                className="home-action-avatar-circle"
                style={{
                  backgroundColor: a.color,
                  zIndex: personaAvatars.length - i,
                }}
              >
                {a.surname}
              </span>
            ))}
            <span className="home-action-avatar-more">+3</span>
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
        <div className="home-recent-row">
          {recentConversations.map((c) => (
            <Link
              key={c.id}
              to={`/chat/${c.id}`}
              className="home-recent-card"
            >
              <span
                className="home-recent-avatar"
                style={{ backgroundColor: c.color }}
              >
                {c.surname}
              </span>
              <div className="home-recent-info">
                <span className="home-recent-name">{c.name}</span>
                <span className="home-recent-time">{c.timeAgo}</span>
              </div>
              <span className="home-recent-grade">{c.grade}</span>
            </Link>
          ))}
        </div>
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
