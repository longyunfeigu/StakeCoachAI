import { useEffect, useState } from 'react'
import { fetchPersonas, fetchScenarios, createRoom, type PersonaSummary, type Scenario } from '../services/api'
import './CreateRoomDialog.css'

interface CreateRoomDialogProps {
  open: boolean
  onClose: () => void
  onCreated: (roomId: number) => void
}

export default function CreateRoomDialog({ open, onClose, onCreated }: CreateRoomDialogProps) {
  const [personas, setPersonas] = useState<PersonaSummary[]>([])
  const [scenarios, setScenarios] = useState<Scenario[]>([])
  const [selectedScenarioId, setSelectedScenarioId] = useState<number | null>(null)
  const [name, setName] = useState('')
  const [type, setType] = useState<'private' | 'group'>('private')
  const [selectedPersonas, setSelectedPersonas] = useState<string[]>([])
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    if (open) {
      fetchPersonas().then(setPersonas).catch(() => {})
      fetchScenarios().then(setScenarios).catch(() => {})
      // Reset form
      setName('')
      setType('private')
      setSelectedPersonas([])
      setSelectedScenarioId(null)
      setError(null)
    }
  }, [open])

  const handleScenarioChange = (scenarioId: number | null) => {
    setSelectedScenarioId(scenarioId)
    if (scenarioId !== null) {
      const scenario = scenarios.find((s) => s.id === scenarioId)
      if (scenario && scenario.suggested_persona_ids.length > 0) {
        setSelectedPersonas(scenario.suggested_persona_ids)
        if (scenario.suggested_persona_ids.length >= 2) {
          setType('group')
        }
      }
    }
  }

  const togglePersona = (id: string) => {
    if (type === 'private') {
      // Private: single select
      setSelectedPersonas((prev) => (prev.includes(id) ? [] : [id]))
    } else {
      // Group: multi select
      setSelectedPersonas((prev) =>
        prev.includes(id) ? prev.filter((p) => p !== id) : [...prev, id]
      )
    }
  }

  // When switching type, reset selection if it violates constraints
  useEffect(() => {
    if (type === 'private' && selectedPersonas.length > 1) {
      setSelectedPersonas([selectedPersonas[0]])
    }
  }, [type])

  const isValid = () => {
    if (!name.trim()) return false
    if (type === 'private' && selectedPersonas.length !== 1) return false
    if (type === 'group' && selectedPersonas.length < 2) return false
    return true
  }

  const handleSubmit = async () => {
    if (!isValid()) return
    setSubmitting(true)
    setError(null)
    try {
      const room = await createRoom({
        name: name.trim(),
        type,
        persona_ids: selectedPersonas,
        ...(selectedScenarioId != null ? { scenario_id: selectedScenarioId } : {}),
      })
      onCreated(room.id)
      onClose()
    } catch (e: any) {
      setError(e.message)
    } finally {
      setSubmitting(false)
    }
  }

  if (!open) return null

  return (
    <div className="dialog-overlay" onClick={onClose}>
      <div className="dialog" onClick={(e) => e.stopPropagation()}>
        <h3>创建聊天室</h3>

        <label className="field-label">
          名称
          <input
            name="name"
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="输入聊天室名称"
            autoFocus
          />
        </label>

        <label className="field-label">
          类型
          <select
            name="type"
            value={type}
            onChange={(e) => setType(e.target.value as 'private' | 'group')}
          >
            <option value="private">私聊</option>
            <option value="group">群聊</option>
          </select>
        </label>

        {scenarios.length > 0 && (
          <label className="field-label">
            场景（可选）
            <select
              value={selectedScenarioId ?? ''}
              onChange={(e) =>
                handleScenarioChange(e.target.value ? Number(e.target.value) : null)
              }
            >
              <option value="">不使用场景</option>
              {scenarios.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </select>
          </label>
        )}

        <div className="field-label">
          选择角色 {type === 'private' ? '(选择 1 个)' : '(至少 2 个)'}
        </div>
        <div className="persona-select-list">
          {personas.map((p) => (
            <div
              key={p.id}
              className={`persona-select-item ${selectedPersonas.includes(p.id) ? 'selected' : ''}`}
              onClick={() => togglePersona(p.id)}
            >
              <span
                className="persona-color"
                style={{ backgroundColor: p.avatar_color || '#999' }}
              />
              <span className="persona-select-name">{p.name}</span>
              <span className="persona-select-role">{p.role}</span>
            </div>
          ))}
        </div>

        {error && <div className="dialog-error">{error}</div>}

        <div className="dialog-actions">
          <button className="btn-cancel" onClick={onClose}>取消</button>
          <button
            className="btn-submit"
            onClick={handleSubmit}
            disabled={!isValid() || submitting}
          >
            {submitting ? '创建中...' : '创建'}
          </button>
        </div>
      </div>
    </div>
  )
}
