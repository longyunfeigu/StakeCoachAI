import { useEffect, useState } from 'react'
import {
  fetchPersonaDetail,
  fetchTeams,
  createPersona,
  updatePersona,
  deletePersona,
  type PersonaSummary,
  type Organization,
  type Team,
} from '../services/api'
import Avatar from './Avatar'
import './PersonaEditorDialog.css'

interface PersonaEditorDialogProps {
  open: boolean
  onClose: () => void
  onSaved: () => void
  editingPersona?: PersonaSummary | null
  currentOrg?: Organization | null
}

export default function PersonaEditorDialog({
  open,
  onClose,
  onSaved,
  editingPersona,
  currentOrg,
}: PersonaEditorDialogProps) {
  const isEdit = !!editingPersona

  const [id, setId] = useState('')
  const [name, setName] = useState('')
  const [role, setRole] = useState('')
  const [avatarColor, setAvatarColor] = useState('#888888')
  const [content, setContent] = useState('')
  const [teamId, setTeamId] = useState<number | null>(null)
  const [teams, setTeams] = useState<Team[]>([])
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!open) return
    setError(null)
    setSubmitting(false)

    // Load teams if org exists
    if (currentOrg) {
      fetchTeams(currentOrg.id).then(setTeams).catch(() => setTeams([]))
    } else {
      setTeams([])
    }

    if (editingPersona) {
      setId(editingPersona.id)
      setName(editingPersona.name)
      setRole(editingPersona.role)
      setAvatarColor(editingPersona.avatar_color || '#888888')
      setTeamId(editingPersona.team_id)
      setContent('')
      setLoading(true)
      fetchPersonaDetail(editingPersona.id)
        .then((detail) => {
          setContent(detail.content || '')
        })
        .catch(() => {
          setContent('')
        })
        .finally(() => setLoading(false))
    } else {
      setId('')
      setName('')
      setRole('')
      setAvatarColor('#888888')
      setTeamId(null)
      setContent('')
      setLoading(false)
    }
  }, [open, editingPersona])

  const handleSave = async () => {
    setSubmitting(true)
    setError(null)
    try {
      const orgFields = {
        organization_id: currentOrg?.id ?? null,
        team_id: teamId,
      }
      if (isEdit) {
        await updatePersona(editingPersona!.id, {
          name,
          role,
          avatar_color: avatarColor,
          content,
          ...orgFields,
        })
      } else {
        if (!id.trim()) {
          setError('ID 不能为空')
          setSubmitting(false)
          return
        }
        await createPersona({
          id: id.trim(),
          name,
          role,
          avatar_color: avatarColor,
          content,
          ...orgFields,
        })
      }
      onSaved()
      onClose()
    } catch (e: any) {
      setError(e.message)
    } finally {
      setSubmitting(false)
    }
  }

  const handleDelete = async () => {
    if (!editingPersona) return
    if (!confirm(`确定删除角色「${editingPersona.name}」？`)) return
    setSubmitting(true)
    try {
      await deletePersona(editingPersona.id)
      onSaved()
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
      <div
        className="dialog persona-editor-dialog"
        onClick={(e) => e.stopPropagation()}
      >
        <h3>{isEdit ? '编辑角色' : '新建角色'}</h3>
        <div className="dialog-body">
          <div className="persona-avatar-preview">
            <Avatar name={name || '?'} color={avatarColor} size={48} />
          </div>

          <label className="field-label">
            ID
            <input
              type="text"
              value={id}
              onChange={(e) => setId(e.target.value)}
              placeholder="英文标识符，如 ceo"
              disabled={isEdit}
              autoFocus={!isEdit}
            />
          </label>

          <label className="field-label">
            名称
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="角色显示名称"
            />
          </label>

          <label className="field-label">
            角色
            <input
              type="text"
              value={role}
              onChange={(e) => setRole(e.target.value)}
              placeholder="如：CEO、产品经理"
            />
          </label>

          <label className="field-label">
            头像颜色
            <div className="color-field">
              <input
                type="color"
                value={avatarColor}
                onChange={(e) => setAvatarColor(e.target.value)}
              />
              <span className="color-value">{avatarColor}</span>
            </div>
          </label>

          {teams.length > 0 && (
            <label className="field-label">
              所属团队
              <select
                value={teamId ?? ''}
                onChange={(e) => setTeamId(e.target.value ? Number(e.target.value) : null)}
              >
                <option value="">不指定</option>
                {teams.map((t) => (
                  <option key={t.id} value={t.id}>{t.name}</option>
                ))}
              </select>
            </label>
          )}

          <label className="field-label">
            内容（Markdown）
            <textarea
              value={loading ? '加载中...' : content}
              onChange={(e) => setContent(e.target.value)}
              placeholder="角色画像的详细内容..."
              disabled={loading}
            />
          </label>

          {error && <div className="dialog-error">{error}</div>}
        </div>

        <div className="dialog-actions">
          {isEdit && (
            <button
              className="btn-delete"
              onClick={handleDelete}
              disabled={submitting}
            >
              删除
            </button>
          )}
          <button className="btn-cancel" onClick={onClose}>
            取消
          </button>
          <button
            className="btn-submit"
            onClick={handleSave}
            disabled={submitting || loading}
          >
            {submitting ? '保存中...' : '保存'}
          </button>
        </div>
      </div>
    </div>
  )
}
