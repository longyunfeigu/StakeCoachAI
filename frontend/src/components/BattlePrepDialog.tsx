import { useState, useEffect } from 'react'
import { Loader2, X, Zap } from 'lucide-react'
import { generateBattlePrep, startBattle, type BattlePrepResult } from '../services/api'
import './BattlePrepDialog.css'

interface Props {
  open: boolean
  onClose: () => void
  onStarted: (roomId: number) => void
}

type Difficulty = 'easy' | 'normal' | 'hard'

const DIFFICULTY_OPTIONS: { value: Difficulty; label: string }[] = [
  { value: 'easy', label: '温和' },
  { value: 'normal', label: '正常' },
  { value: 'hard', label: '强硬' },
]

function resetState() {
  return {
    step: 1 as 1 | 2 | 3,
    description: '',
    loading: false,
    error: null as string | null,
    prepResult: null as BattlePrepResult | null,
    personaName: '',
    personaRole: '',
    personaStyle: '',
    difficulty: 'normal' as Difficulty,
    selectedPoints: [] as string[],
    submitting: false,
  }
}

export default function BattlePrepDialog({ open, onClose, onStarted }: Props) {
  const [state, setState] = useState(resetState)

  // Reset all state whenever the dialog opens
  useEffect(() => {
    if (open) {
      setState(resetState())
    }
  }, [open])

  // Reset when closed via the X / overlay click
  const handleClose = () => {
    setState(resetState())
    onClose()
  }

  // ---- Step 1: generate ----
  const handleGenerate = async () => {
    if (state.description.trim().length < 10) return
    setState((s) => ({ ...s, loading: true, error: null }))
    try {
      const result = await generateBattlePrep(state.description.trim())
      setState((s) => ({
        ...s,
        loading: false,
        prepResult: result,
        personaName: result.persona_name,
        personaRole: result.persona_role,
        personaStyle: result.persona_style,
        selectedPoints: [...result.training_points],
        step: 2,
      }))
    } catch (e: any) {
      setState((s) => ({ ...s, loading: false, error: e.message || '生成失败，请重试' }))
    }
  }

  // ---- Step 3: start battle ----
  const handleStartBattle = async () => {
    if (state.selectedPoints.length === 0 || !state.prepResult) return
    setState((s) => ({ ...s, submitting: true, error: null }))
    try {
      const room = await startBattle({
        persona_name: state.personaName,
        persona_role: state.personaRole,
        persona_style: state.personaStyle,
        scenario_context: state.prepResult.scenario_context,
        selected_training_points: state.selectedPoints,
        difficulty: state.difficulty,
      })
      setState(resetState())
      onStarted(room.id)
      onClose()
    } catch (e: any) {
      setState((s) => ({ ...s, submitting: false, error: e.message || '启动失败，请重试' }))
    }
  }

  const togglePoint = (point: string) => {
    setState((s) => ({
      ...s,
      selectedPoints: s.selectedPoints.includes(point)
        ? s.selectedPoints.filter((p) => p !== point)
        : [...s.selectedPoints, point],
    }))
  }

  if (!open) return null

  const { step, description, loading, error, prepResult, personaName, personaRole, personaStyle, difficulty, selectedPoints, submitting } = state

  return (
    <div className="bp-overlay" onClick={handleClose}>
      <div className="bp-dialog" onClick={(e) => e.stopPropagation()}>
        {/* Top accent bar */}
        <div className="bp-accent-bar" />

        {/* Header */}
        <div className="bp-header">
          <div className="bp-title">
            <Zap size={18} className="bp-title-icon" />
            紧急备战
          </div>
          <button className="bp-close-btn" onClick={handleClose} aria-label="关闭">
            <X size={18} />
          </button>
        </div>

        {/* Step indicator */}
        <div className="bp-step-indicator">
          {[1, 2, 3].map((n) => (
            <div key={n} className="bp-step-item">
              <div className={`bp-step-dot ${step === n ? 'active' : step > n ? 'done' : ''}`}>
                {n}
              </div>
              <span className={`bp-step-label ${step === n ? 'active' : ''}`}>
                {n === 1 ? '描述会议' : n === 2 ? '预览角色' : '选择训练点'}
              </span>
              {n < 3 && <div className={`bp-step-line ${step > n ? 'done' : ''}`} />}
            </div>
          ))}
        </div>

        {/* Body */}
        <div className="bp-body">
          {/* ---- Step 1 ---- */}
          {step === 1 && (
            <div className="bp-step-content">
              <p className="bp-hint">详细描述你即将参加的会议，AI 将为你生成专属对手角色。</p>
              <textarea
                className="bp-textarea"
                value={description}
                onChange={(e) => setState((s) => ({ ...s, description: e.target.value }))}
                placeholder="描述你即将参加的会议：跟谁谈、谈什么、你的目标是什么、对方可能的态度..."
                rows={6}
                disabled={loading}
              />
              {error && <div className="bp-error">{error}</div>}
              <div className="bp-actions">
                <button className="btn-cancel" onClick={handleClose}>取消</button>
                <button
                  className="btn-submit"
                  onClick={handleGenerate}
                  disabled={description.trim().length < 10 || loading}
                >
                  {loading ? (
                    <span className="bp-loading-inline">
                      <Loader2 size={15} className="bp-spinner" />
                      AI 正在分析...
                    </span>
                  ) : '下一步'}
                </button>
              </div>
            </div>
          )}

          {/* ---- Step 2 ---- */}
          {step === 2 && prepResult && (
            <div className="bp-step-content">
              <p className="bp-hint">AI 已生成对手角色，你可以在此调整。</p>

              <div className="bp-persona-card">
                <label className="bp-field-label">
                  角色名称
                  <input
                    type="text"
                    className="bp-input"
                    value={personaName}
                    onChange={(e) => setState((s) => ({ ...s, personaName: e.target.value }))}
                  />
                </label>
                <label className="bp-field-label">
                  职位 / 角色
                  <input
                    type="text"
                    className="bp-input"
                    value={personaRole}
                    onChange={(e) => setState((s) => ({ ...s, personaRole: e.target.value }))}
                  />
                </label>
                <label className="bp-field-label">
                  风格描述
                  <textarea
                    className="bp-textarea bp-textarea--sm"
                    value={personaStyle}
                    onChange={(e) => setState((s) => ({ ...s, personaStyle: e.target.value }))}
                    rows={3}
                  />
                </label>
              </div>

              <div className="bp-difficulty">
                <div className="bp-field-label">难度</div>
                <div className="bp-radio-group">
                  {DIFFICULTY_OPTIONS.map((opt) => (
                    <label key={opt.value} className={`bp-radio-item ${difficulty === opt.value ? 'selected' : ''}`}>
                      <input
                        type="radio"
                        name="difficulty"
                        value={opt.value}
                        checked={difficulty === opt.value}
                        onChange={() => setState((s) => ({ ...s, difficulty: opt.value }))}
                      />
                      {opt.label}
                    </label>
                  ))}
                </div>
              </div>

              {error && <div className="bp-error">{error}</div>}
              <div className="bp-actions">
                <button className="btn-cancel" onClick={() => setState((s) => ({ ...s, step: 1, error: null }))}>
                  上一步
                </button>
                <button
                  className="btn-submit"
                  onClick={() => setState((s) => ({ ...s, step: 3, error: null }))}
                  disabled={!personaName.trim() || !personaRole.trim()}
                >
                  确认角色
                </button>
              </div>
            </div>
          )}

          {/* ---- Step 3 ---- */}
          {step === 3 && prepResult && (
            <div className="bp-step-content">
              <p className="bp-hint">选择本次想要练习的训练点（至少选 1 个）。</p>
              <div className="bp-training-list">
                {prepResult.training_points.map((point) => (
                  <label key={point} className="bp-checkbox-item">
                    <input
                      type="checkbox"
                      checked={selectedPoints.includes(point)}
                      onChange={() => togglePoint(point)}
                    />
                    <span>{point}</span>
                  </label>
                ))}
              </div>

              {error && <div className="bp-error">{error}</div>}
              <div className="bp-actions">
                <button
                  className="btn-cancel"
                  onClick={() => setState((s) => ({ ...s, step: 2, error: null }))}
                  disabled={submitting}
                >
                  上一步
                </button>
                <button
                  className="btn-submit"
                  onClick={handleStartBattle}
                  disabled={selectedPoints.length === 0 || submitting}
                >
                  {submitting ? (
                    <span className="bp-loading-inline">
                      <Loader2 size={15} className="bp-spinner" />
                      启动中...
                    </span>
                  ) : '开始备战'}
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
