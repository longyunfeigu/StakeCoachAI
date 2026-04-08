import './Avatar.css'

interface AvatarProps {
  name: string
  color?: string
  size?: number
}

function getInitial(name: string): string {
  if (!name) return '?'
  const ch = name.charAt(0)
  // If ASCII letter, uppercase it
  if (/[a-zA-Z]/.test(ch)) return ch.toUpperCase()
  // Chinese / other characters — return as-is
  return ch
}

export default function Avatar({ name, color = '#2D9C6F', size = 36 }: AvatarProps) {
  return (
    <div
      className="sc-avatar"
      style={{
        width: size,
        height: size,
        fontSize: size * 0.44,
        background: color,
      }}
      title={name}
    >
      {getInitial(name)}
    </div>
  )
}
