import { useEffect, useState } from 'react'
import {
  fetchPersonaDetail,
  createPersona,
  updatePersona,
  deletePersona,
  type PersonaSummary,
} from '../services/api'
import './PersonaEditorDialog.css'

interface PersonaEditorDialogProps {
  open: boolean
  onClose: () => void
  onSaved: () => void
  editingPersona?: PersonaSummary | null
}

export default function PersonaEditorDialog({
  open,
  onClose,
  onSaved,
  editingPersona,
}: PersonaEditorDialogProps) {
  const isEdit = !!editingPersona

  const [id, setId] = useState('')
  const [name, setName] = useState('')
  const [role, setRole] = useState('')
  const [avatarColor, setAvatarColor] = useState('#888888')
  const [content, setContent] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!open) return
    setError(null)
    setSubmitting(false)

    if (editingPersona) {
      setId(editingPersona.id)
      setName(editingPersona.name)
      setRole(editingPersona.role)
      setAvatarColor(editingPersona.avatar_color || '#888888')
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
      setContent('')
      setLoading(false)
    }
  }, [open, editingPersona])

  const handleSave = async () => {
    setSubmitting(true)
    setError(null)
    try {
      if (isEdit) {
        await updatePersona(editingPersona!.id, {
          name,
          role,
          avatar_color: avatarColor,
          content,
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
