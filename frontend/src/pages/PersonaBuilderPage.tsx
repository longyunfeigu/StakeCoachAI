// input: route /persona/new
// output: 输入素材（1-5 段，类型 tag）+ SSE 流式进度面板 + 失败重试 + 完成 2s 自动跳转
// owner: wanhua.gu
// pos: 表示层 - persona builder 入口页 (Story 2.6 AC1-10)；一旦我被更新，务必更新我的开头注释以及所属文件夹的md
import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Plus, Sparkles, RotateCcw, X, ArrowRight } from 'lucide-react'
import { usePersonaBuild } from '../hooks/usePersonaBuild'
import PersonaBuildProgress from '../components/PersonaBuildProgress'
import './PersonaBuilderPage.css'

type SegmentType = 'chat' | 'email' | 'meeting' | 'other'
const SEGMENT_TAGS: { type: SegmentType; label: string; klass: string }[] = [
  { type: 'chat', label: '聊天', klass: 'tag-chat' },
  { type: 'email', label: '邮件', klass: 'tag-email' },
  { type: 'meeting', label: '纪要', klass: 'tag-meeting' },
  { type: 'other', label: '其他', klass: 'tag-other' },
]

interface Segment {
  id: string
  text: string
  type: SegmentType
}

const MAX_SEGMENTS = 5
const CHAR_LIMIT = 400_000

function newSegment(): Segment {
  return { id: Math.random().toString(36).slice(2), text: '', type: 'chat' }
}

function placeholderFor(type: SegmentType): string {
  switch (type) {
    case 'chat':
      return '粘贴聊天记录，例如：\n张三 09:21\n这个方案下周必须上线\n李四 09:22\n时间太紧…'
    case 'email':
      return '粘贴邮件正文…'
    case 'meeting':
      return '粘贴会议纪要…'
    default:
      return '粘贴任何相关文本…'
  }
}

export default function PersonaBuilderPage() {
  const navigate = useNavigate()
  const [segments, setSegments] = useState<Segment[]>([newSegment()])
  const [name, setName] = useState('')
  const [role, setRole] = useState('')

  const { status, events, personaId, error, start, reset } = usePersonaBuild()

  const totalChars = useMemo(
    () => segments.reduce((sum, s) => sum + s.text.length, 0),
    [segments],
  )
  const cleanedMaterials = useMemo(
    () => segments.map((s) => s.text.trim()).filter(Boolean),
    [segments],
  )
  const canSubmit =
    status !== 'running' &&
    cleanedMaterials.length > 0 &&
    totalChars <= CHAR_LIMIT

  // AC8: persist_done 后 2 秒自动跳转
  useEffect(() => {
    if (status === 'done' && personaId) {
      const t = setTimeout(() => navigate(`/persona/${personaId}/edit`), 2000)
      return () => clearTimeout(t)
    }
  }, [status, personaId, navigate])

  // AC9 (partial): 浏览器关闭/刷新时拦截。SPA 内 <Link> 切换在声明式 Routes
  // 模式下 react-router v7 没有原生 useBlocker — 此 AC 部分通过。
  useEffect(() => {
    if (status !== 'running') return
    const handler = (e: BeforeUnloadEvent) => {
      e.preventDefault()
      e.returnValue = ''
    }
    window.addEventListener('beforeunload', handler)
    return () => window.removeEventListener('beforeunload', handler)
  }, [status])

  const addSegment = () => {
    if (segments.length >= MAX_SEGMENTS) return
    setSegments((prev) => [...prev, newSegment()])
  }
  const removeSegment = (id: string) => {
    setSegments((prev) => (prev.length <= 1 ? prev : prev.filter((s) => s.id !== id)))
  }
  const updateSegment = (id: string, patch: Partial<Segment>) => {
    setSegments((prev) => prev.map((s) => (s.id === id ? { ...s, ...patch } : s)))
  }

  const handleStart = () => {
    if (!canSubmit) return
    start({
      materials: cleanedMaterials,
      name: name.trim() || undefined,
      role: role.trim() || undefined,
    })
  }

  const handleRetry = () => {
    reset()
    setTimeout(() => handleStart(), 0)
  }

  const handleManualGoto = () => {
    if (personaId) navigate(`/persona/${personaId}/edit`)
  }

  return (
    <div className="persona-builder">
      <header className="builder-header">
        <h1>从素材生成对手</h1>
        <p>粘贴 1-5 段聊天记录 / 邮件 / 会议纪要，让 AI 在 2-3 分钟内分析出对手画像</p>
      </header>

      <div className="builder-grid">
        {/* === 左侧：素材输入 === */}
        <section className="input-pane">
          <div className="builder-meta">
            <label className="meta-field">
              <span>角色名（可选）</span>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="留空让 AI 提炼"
                disabled={status === 'running'}
              />
            </label>
            <label className="meta-field">
              <span>职位（可选）</span>
              <input
                type="text"
                value={role}
                onChange={(e) => setRole(e.target.value)}
                placeholder="留空让 AI 提炼"
                disabled={status === 'running'}
              />
            </label>
          </div>

          <div className="segments-list">
            {segments.map((seg, idx) => (
              <div key={seg.id} className="input-segment">
                <div className="segment-head">
                  <span className="segment-index">素材 #{idx + 1}</span>
                  <div className="segment-tags">
                    {SEGMENT_TAGS.map((t) => (
                      <button
                        key={t.type}
                        type="button"
                        className={`type-tag ${t.klass} ${seg.type === t.type ? 'active' : ''}`}
                        onClick={() => updateSegment(seg.id, { type: t.type })}
                        disabled={status === 'running'}
                      >
                        {t.label}
                      </button>
                    ))}
                  </div>
                  {segments.length > 1 && (
                    <button
                      type="button"
                      className="segment-remove"
                      onClick={() => removeSegment(seg.id)}
                      disabled={status === 'running'}
                      title="删除这段"
                    >
                      <X size={14} />
                    </button>
                  )}
                </div>
                <textarea
                  className="segment-textarea"
                  value={seg.text}
                  onChange={(e) => updateSegment(seg.id, { text: e.target.value })}
                  placeholder={placeholderFor(seg.type)}
                  disabled={status === 'running'}
                  rows={6}
                />
              </div>
            ))}
          </div>

          <button
            type="button"
            className="add-segment-btn"
            onClick={addSegment}
            disabled={segments.length >= MAX_SEGMENTS || status === 'running'}
          >
            <Plus size={14} />
            添加素材（{segments.length} / {MAX_SEGMENTS}）
          </button>

          <div className="builder-footer">
            <span className={`char-count ${totalChars > CHAR_LIMIT ? 'over' : ''}`}>
              {totalChars.toLocaleString()} / {CHAR_LIMIT.toLocaleString()} 字符
            </span>
            {status === 'error' && (
              <button type="button" className="btn-retry retry" onClick={handleRetry}>
                <RotateCcw size={14} />
                重试
              </button>
            )}
            {status === 'done' && personaId && (
              <button type="button" className="btn-goto" onClick={handleManualGoto}>
                查看结果
                <ArrowRight size={14} />
              </button>
            )}
            <button
              type="button"
              className="btn-start"
              onClick={handleStart}
              disabled={!canSubmit}
            >
              <Sparkles size={14} />
              {status === 'running' ? '分析中…' : '开始分析'}
            </button>
          </div>
        </section>

        {/* === 右侧：进度面板 === */}
        <aside className="progress-pane">
          <PersonaBuildProgress events={events} status={status} error={error} />
        </aside>
      </div>

      {/* AC7: 失败 toast — 顶部固定提示条 */}
      {status === 'error' && error && (
        <div className="builder-toast">
          <X size={14} />
          <span>分析失败：{error.message}</span>
        </div>
      )}
    </div>
  )
}
