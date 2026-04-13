// input: evidence (EvidenceItem|null), anchor (DOMRect|null), onClose
// output: 320px 浮层 (>1180px) 或底部 sheet (≤1180px) 展示 claim + 置信度 gauge + citations
// owner: wanhua.gu
// pos: 表示层 - persona editor 证据 popover (Story 2.7 AC)；一旦我被更新，务必更新我的开头注释以及所属文件夹的md
import { useEffect, useState } from 'react'
import { X, MessageSquare, Mail, FileText } from 'lucide-react'
import type { EvidenceItem } from '../../services/personaV2'

interface Props {
  evidence: EvidenceItem | null
  anchor: DOMRect | null
  onClose: () => void
}

function inferSourceIcon(materialId: string) {
  if (/chat|msg|im/i.test(materialId)) return <MessageSquare size={12} />
  if (/mail|email/i.test(materialId)) return <Mail size={12} />
  return <FileText size={12} />
}

export default function EvidencePopover({ evidence, anchor, onClose }: Props) {
  const [isMobile, setIsMobile] = useState(
    typeof window !== 'undefined' ? window.innerWidth <= 1180 : false,
  )

  useEffect(() => {
    const onResize = () => setIsMobile(window.innerWidth <= 1180)
    window.addEventListener('resize', onResize)
    return () => window.removeEventListener('resize', onResize)
  }, [])

  useEffect(() => {
    if (!evidence) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [evidence, onClose])

  if (!evidence) return null

  const radius = 32
  const circumference = 2 * Math.PI * radius
  const clampedConfidence = Math.max(0, Math.min(1, evidence.confidence))
  const dashOffset = circumference * (1 - clampedConfidence)

  const inner = (
    <>
      <div className="pop-title">{evidence.claim}</div>
      <div className="gauge">
        <svg viewBox="0 0 80 80">
          <circle
            cx="40"
            cy="40"
            r={radius}
            stroke="var(--green-soft)"
            strokeWidth="6"
            fill="none"
          />
          <circle
            cx="40"
            cy="40"
            r={radius}
            stroke="var(--green)"
            strokeWidth="6"
            fill="none"
            strokeDasharray={circumference}
            strokeDashoffset={dashOffset}
            strokeLinecap="round"
            transform="rotate(-90 40 40)"
          />
        </svg>
        <div>
          <div className="num">{evidence.confidence.toFixed(2)}</div>
          <div className="lbl">置信度</div>
        </div>
      </div>
      {evidence.citations.length === 0 ? (
        <div className="pop-empty">暂无原文引用</div>
      ) : (
        evidence.citations.map((c, i) => (
          <div key={i} className="pop-cite">
            <div className="cite-icon">{inferSourceIcon(evidence.source_material_id)}</div>
            <div className="cite-body">
              <div className="cite-time">{evidence.source_material_id}</div>
              <div className="cite-text">&ldquo;{c}&rdquo;</div>
            </div>
          </div>
        ))
      )}
    </>
  )

  if (isMobile) {
    return (
      <div className="evidence-sheet-overlay" onClick={onClose}>
        <div className="evidence-sheet" onClick={(e) => e.stopPropagation()}>
          <button type="button" className="sheet-close" onClick={onClose} aria-label="关闭">
            <X size={16} />
          </button>
          {inner}
        </div>
      </div>
    )
  }

  // Desktop popover anchored to feature row
  const top = anchor ? anchor.top + anchor.height / 2 : 200
  // Position to the right of anchor; if no room, flip to left
  let left = anchor ? anchor.right + 16 : 200
  const viewW = typeof window !== 'undefined' ? window.innerWidth : 1280
  if (anchor && left + 320 > viewW - 24) {
    left = Math.max(24, anchor.left - 320 - 16)
  }

  return (
    <div
      className="evidence-popover popover"
      style={{
        position: 'fixed',
        top,
        left,
        transform: 'translateY(-50%)',
        zIndex: 50,
      }}
    >
      {inner}
    </div>
  )
}
