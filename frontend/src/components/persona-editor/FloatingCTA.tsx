// input: hasUnsaved, saving, onSave, onStartBattle
// output: 底部固定 CTA bar — 保存备用 (ghost) + 开始演练 (primary gradient)
// owner: wanhua.gu
// pos: 表示层 - persona editor 底部 CTA (Story 2.7 AC)；一旦我被更新，务必更新我的开头注释以及所属文件夹的md
import { Rocket, Save, PlusCircle } from 'lucide-react'

interface Props {
  hasUnsaved: boolean
  saving: boolean
  onSave: () => void
  onStartBattle: () => void
  onEnhance?: () => void
  showEnhance?: boolean
}

export default function FloatingCTA({
  hasUnsaved,
  saving,
  onSave,
  onStartBattle,
  onEnhance,
  showEnhance = true,
}: Props) {
  return (
    <div className="cta">
      {showEnhance && onEnhance && (
        <button type="button" className="btn-ghost" onClick={onEnhance}>
          <PlusCircle size={14} style={{ marginRight: 6, verticalAlign: -2 }} />
          追加素材
        </button>
      )}
      <button
        type="button"
        className="btn-ghost"
        onClick={onSave}
        disabled={!hasUnsaved || saving}
      >
        <Save size={14} style={{ marginRight: 6, verticalAlign: -2 }} />
        {saving ? '保存中…' : hasUnsaved ? '💾 保存备用' : '已保存'}
      </button>
      <button type="button" className="btn-go" onClick={onStartBattle}>
        <Rocket size={14} style={{ marginRight: 6, verticalAlign: -2 }} />
        🚀 开始演练
      </button>
    </div>
  )
}
