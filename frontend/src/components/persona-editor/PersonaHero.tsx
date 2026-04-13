// input: persona (PersonaV2), strength (0..1), evidenceCount, materialCount
// output: Hero card 组件 — 圆形头像 (conic ring + pulse dot) + 名字 + strength 进度条
// owner: wanhua.gu
// pos: 表示层 - persona editor Hero (Story 2.7 AC 设计基线)；一旦我被更新，务必更新我的开头注释以及所属文件夹的md
import type { PersonaV2 } from '../../services/personaV2'

interface Props {
  persona: PersonaV2
  strength: number // 0..1
  evidenceCount: number
  materialCount: number
}

function getInitial(name: string): string {
  return name.trim().charAt(0).toUpperCase() || '?'
}

export default function PersonaHero({
  persona,
  strength,
  evidenceCount,
  materialCount,
}: Props) {
  const pct = Math.round(strength * 100)
  const innerStyle: React.CSSProperties = persona.avatar_color
    ? { background: persona.avatar_color }
    : {}
  return (
    <div className="persona-hero">
      <div className="avatar-big">
        <div className="ring" />
        <div className="inner" style={innerStyle}>
          {getInitial(persona.name)}
        </div>
        <div className="pulse" />
      </div>
      <div className="hero-info">
        <h1>{persona.name}</h1>
        <div className="sub">{persona.role || '—'}</div>
        <div className="tags">
          <span className="pill">v{persona.schema_version}</span>
          {persona.identity?.hidden_agenda && <span className="pill alt">🕶️ 隐藏议程</span>}
          {strength < 0.6 && <span className="pill warn">⚠ 证据偏弱</span>}
        </div>
      </div>
      <div className="strength">
        <div className="label">
          <span>Persona Strength</span>
          <b>{pct}%</b>
        </div>
        <div className="bar">
          <div className="fill" style={{ width: `${pct}%` }} />
        </div>
        <div className="meta">
          基于 {materialCount} 条素材 · {evidenceCount} 条引用支撑
        </div>
      </div>
    </div>
  )
}
