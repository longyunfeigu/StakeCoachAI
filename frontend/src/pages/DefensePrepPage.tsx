import { useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Loader2, Upload, FileText, ArrowLeft, Play } from 'lucide-react'
import { createDefenseSession, startDefenseSession, type DefenseSession, type PersonaSummary } from '../services/api'
import { useAppContext } from '../contexts/AppContext'
import './DefensePrepPage.css'

const SCENARIO_OPTIONS: { value: string; label: string; desc: string }[] = [
  { value: 'performance_review', label: '绩效评审', desc: '年度/季度绩效汇报' },
  { value: 'proposal_review', label: '方案评审', desc: '技术/业务方案答辩' },
  { value: 'project_report', label: '项目汇报', desc: '项目进度与成果展示' },
  { value: 'general', label: '通用答辩', desc: '自定义答辩场景' },
]

const AVATAR_COLORS = ['#8B5226', '#1E3A5F', '#3D2E5C', '#6B4226', '#2E4A3F', '#4A3060']

function getAvatarColor(id: string): string {
  const hash = id.split('').reduce((a, c) => a + c.charCodeAt(0), 0)
  return AVATAR_COLORS[hash % AVATAR_COLORS.length]
}

function initialState() {
  return {
    step: 1 as 1 | 2,
    file: null as File | null,
    selectedPersonaId: '',
    scenarioType: '',
    loading: false,
    error: null as string | null,
    session: null as DefenseSession | null,
    submitting: false,
    dragOver: false,
  }
}

export default function DefensePrepPage() {
  const navigate = useNavigate()
  const { personaMap } = useAppContext()
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [state, setState] = useState(initialState)

  const {
    step,
    file,
    selectedPersonaId,
    scenarioType,
    loading,
    error,
    session,
    submitting,
    dragOver,
  } = state

  const personas: PersonaSummary[] = Object.values(personaMap)

  // ---- File handling ----
  const handleFileChange = (f: File | null) => {
    if (f) {
      setState((s) => ({ ...s, file: f, error: null }))
    }
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setState((s) => ({ ...s, dragOver: false }))
    const f = e.dataTransfer.files?.[0]
    if (f) handleFileChange(f)
  }

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault()
    setState((s) => ({ ...s, dragOver: true }))
  }

  const handleDragLeave = () => {
    setState((s) => ({ ...s, dragOver: false }))
  }

  // ---- Step 1: upload and create session ----
  const handleUpload = async () => {
    if (!file || !selectedPersonaId || !scenarioType) return
    setState((s) => ({ ...s, loading: true, error: null }))
    try {
      const sess = await createDefenseSession(file, selectedPersonaId, scenarioType)
      setState((s) => ({
        ...s,
        loading: false,
        session: sess,
        step: 2,
      }))
    } catch (e: any) {
      setState((s) => ({ ...s, loading: false, error: e.message || '创建失败，请重试' }))
    }
  }

  // ---- Step 2: start session and navigate to chat ----
  const handleStart = async () => {
    if (!session) return
    setState((s) => ({ ...s, submitting: true, error: null }))
    try {
      const updated = await startDefenseSession(session.id)
      if (updated.room_id) {
        navigate(`/chat/${updated.room_id}`)
      } else {
        setState((s) => ({ ...s, submitting: false, error: '未能创建聊天房间，请重试' }))
      }
    } catch (e: any) {
      setState((s) => ({ ...s, submitting: false, error: e.message || '启动失败，请重试' }))
    }
  }

  const selectedPersona = selectedPersonaId ? personaMap[selectedPersonaId] : null
  const selectedScenario = SCENARIO_OPTIONS.find((o) => o.value === scenarioType)
  const questions = session?.question_strategy?.questions ?? []

  return (
    <div className="dp-page">
      <div className="dp-container">
        {/* Back link */}
        <button className="dp-back" onClick={() => navigate('/')}>
          <ArrowLeft size={16} />
          <span>返回首页</span>
        </button>

        {/* Title */}
        <div className="dp-title-row">
          <FileText size={22} className="dp-title-icon" />
          <h1 className="dp-title">答辩准备</h1>
        </div>

        {/* Step indicator */}
        <div className="dp-steps">
          {[1, 2].map((n) => (
            <div key={n} className="dp-step-item">
              <div className={`dp-step-dot ${step === n ? 'active' : step > n ? 'done' : ''}`}>
                {n}
              </div>
              <span className={`dp-step-label ${step === n ? 'active' : ''}`}>
                {n === 1 ? '上传文档' : '确认开始'}
              </span>
              {n < 2 && <div className={`dp-step-line ${step > n ? 'done' : ''}`} />}
            </div>
          ))}
        </div>

        {/* ---- Step 1: Upload + Select ---- */}
        {step === 1 && (
          <div className="dp-card">
            <p className="dp-hint">
              上传你的汇报文档，选择答辩官和场景类型，AI 将为你生成针对性的答辩问题。
            </p>

            {/* File upload */}
            <div className="dp-section-label">上传文档</div>
            {!file ? (
              <div
                className={`dp-upload-area ${dragOver ? 'drag-over' : ''}`}
                onClick={() => fileInputRef.current?.click()}
                onDrop={handleDrop}
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
              >
                <Upload size={28} className="dp-upload-icon" />
                <span className="dp-upload-text">点击或拖拽上传文件</span>
                <span className="dp-upload-hint">支持 PDF、Word、PPT、Markdown 等格式</span>
              </div>
            ) : (
              <div className="dp-file-selected">
                <FileText size={20} className="dp-file-icon" />
                <span className="dp-file-name">{file.name}</span>
                <button
                  className="dp-file-remove"
                  onClick={() => setState((s) => ({ ...s, file: null }))}
                >
                  移除
                </button>
              </div>
            )}
            <input
              ref={fileInputRef}
              type="file"
              className="dp-file-input"
              onChange={(e) => handleFileChange(e.target.files?.[0] ?? null)}
            />

            {/* Persona selection */}
            <div className="dp-section-label">选择答辩官</div>
            <div className="dp-persona-grid">
              {personas.map((p) => (
                <button
                  key={p.id}
                  type="button"
                  className={`dp-persona-card ${selectedPersonaId === p.id ? 'selected' : ''}`}
                  onClick={() => setState((s) => ({ ...s, selectedPersonaId: p.id }))}
                >
                  <span
                    className="dp-persona-avatar"
                    style={{ backgroundColor: p.avatar_color || getAvatarColor(p.id) }}
                  >
                    {p.name.charAt(0)}
                  </span>
                  <span className="dp-persona-name">{p.name}</span>
                  <span className="dp-persona-role">{p.role}</span>
                </button>
              ))}
            </div>

            {/* Scenario selection */}
            <div className="dp-section-label">答辩场景</div>
            <div className="dp-scenario-grid">
              {SCENARIO_OPTIONS.map((opt) => (
                <button
                  key={opt.value}
                  type="button"
                  className={`dp-scenario-card ${scenarioType === opt.value ? 'selected' : ''}`}
                  onClick={() => setState((s) => ({ ...s, scenarioType: opt.value }))}
                >
                  <span className="dp-scenario-label">{opt.label}</span>
                  <span className="dp-scenario-desc">{opt.desc}</span>
                </button>
              ))}
            </div>

            {error && <div className="dp-error">{error}</div>}

            <div className="dp-actions">
              <button
                className="dp-btn-primary"
                onClick={handleUpload}
                disabled={!file || !selectedPersonaId || !scenarioType || loading}
              >
                {loading ? (
                  <span className="dp-loading-inline">
                    <Loader2 size={16} className="dp-spinner" />
                    AI 正在准备...
                  </span>
                ) : (
                  <>
                    <Upload size={14} />
                    上传并准备
                  </>
                )}
              </button>
            </div>
          </div>
        )}

        {/* ---- Step 2: Confirm + Start ---- */}
        {step === 2 && session && (
          <div className="dp-card">
            <p className="dp-hint">AI 已完成分析，以下是答辩准备概要，确认后即可开始模拟答辩。</p>

            {/* Summary */}
            <div className="dp-summary">
              <div className="dp-summary-row">
                <span className="dp-summary-label">文档</span>
                <span className="dp-summary-value">{session.document_title}</span>
              </div>
              <div className="dp-summary-row">
                <span className="dp-summary-label">答辩官</span>
                <span className="dp-summary-value">{selectedPersona?.name ?? session.persona_id}</span>
              </div>
              <div className="dp-summary-row">
                <span className="dp-summary-label">场景</span>
                <span className="dp-summary-value">{selectedScenario?.label ?? session.scenario_type}</span>
              </div>
            </div>

            {/* Question preview */}
            {questions.length > 0 && (
              <>
                <div className="dp-section-label">预设问题 ({questions.length})</div>
                <div className="dp-question-list">
                  {questions.map((q, i) => (
                    <div key={i} className="dp-question-item">
                      <span className="dp-question-index">{i + 1}</span>
                      <div className="dp-question-text">
                        {q.question}
                        <div className="dp-question-meta">
                          <span className="dp-question-badge">{q.dimension}</span>
                          <span className="dp-question-badge">{q.difficulty}</span>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </>
            )}

            {error && <div className="dp-error">{error}</div>}

            <div className="dp-actions dp-actions--split">
              <button
                className="dp-btn-secondary"
                onClick={() => setState((s) => ({ ...s, step: 1, error: null }))}
              >
                <ArrowLeft size={14} />
                上一步
              </button>
              <button
                className="dp-btn-primary"
                onClick={handleStart}
                disabled={submitting}
              >
                {submitting ? (
                  <span className="dp-loading-inline">
                    <Loader2 size={16} className="dp-spinner" />
                    启动中...
                  </span>
                ) : (
                  <>
                    <Play size={14} />
                    开始模拟答辩
                  </>
                )}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
