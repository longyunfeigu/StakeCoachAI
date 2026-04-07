import { useEffect, useState } from 'react'
import { fetchPersonas, fetchPersonaDetail, type PersonaSummary, type PersonaDetail } from '../services/api'
import './PersonaList.css'

export default function PersonaList() {
  const [personas, setPersonas] = useState<PersonaSummary[]>([])
  const [selected, setSelected] = useState<PersonaDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetchPersonas()
      .then(setPersonas)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  const handleClick = async (id: string) => {
    try {
      const detail = await fetchPersonaDetail(id)
      setSelected(detail)
    } catch (e: any) {
      setError(e.message)
    }
  }

  if (loading) return <div className="persona-list">Loading...</div>
  if (error) return <div className="persona-list">Error: {error}</div>

  if (personas.length === 0) {
    return (
      <div className="persona-list">
        <div className="empty-state">暂无可用角色，请在画像目录中添加 Markdown 文件</div>
      </div>
    )
  }

  return (
    <div className="persona-list">
      <h3>角色列表</h3>
      {personas.map((p) => (
        <div
          key={p.id}
          className={`persona-item ${selected?.id === p.id ? 'active' : ''}`}
          onClick={() => handleClick(p.id)}
        >
          <span
            className="persona-color"
            style={{ backgroundColor: p.avatar_color || '#999' }}
          />
          <div className="persona-info">
            <span className="persona-name">{p.name}</span>
            <span className="persona-role">{p.role}</span>
          </div>
        </div>
      ))}

      {selected && (
        <div className="persona-detail">
          <h4>{selected.name}</h4>
          <p className="persona-role-detail">{selected.role}</p>
          <p className="persona-summary">{selected.profile_summary}</p>
        </div>
      )}
    </div>
  )
}
