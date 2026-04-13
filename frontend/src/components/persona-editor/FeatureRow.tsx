// input: emoji, text, onChange? (双击编辑), onShowEvidence? (查证据 popover), onReject? (标记不对), rejected, lowConfidence, evidenceFocused
// output: 单条特征行 — emoji + 文本 + icon 操作按钮
// owner: wanhua.gu
// pos: 表示层 - persona editor 特征行 (Story 2.7 AC)；一旦我被更新，务必更新我的开头注释以及所属文件夹的md
import { useEffect, useRef, useState } from 'react'
import { Search, X } from 'lucide-react'

interface Props {
  emoji: string
  text: string
  onChange?: (newText: string) => void
  onShowEvidence?: (anchor: HTMLElement) => void
  onReject?: () => void
  rejected?: boolean
  lowConfidence?: boolean
  evidenceFocused?: boolean
}

export default function FeatureRow(props: Props) {
  const [editing, setEditing] = useState(false)
  // Draft is seeded from props.text only when entering edit mode; during edit
  // it's fully controlled by the input's onChange.
  const [draft, setDraft] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)
  const rowRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (editing) inputRef.current?.focus()
  }, [editing])

  const startEdit = () => {
    if (!props.onChange) return
    setDraft(props.text)
    setEditing(true)
  }
  const commit = () => {
    setEditing(false)
    if (draft !== props.text && props.onChange) props.onChange(draft)
  }
  const cancel = () => {
    setEditing(false)
  }

  const classes = [
    'feature-row',
    'feature',
    props.rejected ? 'rejected' : '',
    props.lowConfidence ? 'warn' : '',
    props.evidenceFocused ? 'focused' : '',
  ]
    .filter(Boolean)
    .join(' ')

  return (
    <div ref={rowRef} className={classes} onDoubleClick={startEdit}>
      <span className="emoji">{props.emoji}</span>
      <div className="text">
        {editing ? (
          <input
            ref={inputRef}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onBlur={commit}
            onKeyDown={(e) => {
              if (e.key === 'Enter') commit()
              else if (e.key === 'Escape') cancel()
            }}
            className="feature-edit-input"
          />
        ) : (
          <span>{props.text}</span>
        )}
      </div>
      {props.lowConfidence && <span className="warn-chip">⚠ 证据不足</span>}
      <div className="acts">
        {props.onShowEvidence && (
          <button
            type="button"
            className={`icon-circ evidence-btn ${props.evidenceFocused ? 'focused' : ''}`}
            onClick={() => props.onShowEvidence!(rowRef.current!)}
            title="查证据"
          >
            <Search size={13} />
          </button>
        )}
        {props.onReject && (
          <button
            type="button"
            className="icon-circ reject-btn"
            onClick={props.onReject}
            title={props.rejected ? '取消标记' : '标记不对'}
          >
            <X size={13} />
          </button>
        )}
      </div>
    </div>
  )
}
