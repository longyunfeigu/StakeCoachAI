// input: route /persona/:id/edit
// output: 完整编辑器 (Hero + 5 LayerCards + EvidencePopover + FloatingCTA + 未保存离开确认)
// owner: wanhua.gu
// pos: 表示层 - 5-layer persona 编辑器主页 (Story 2.7)；一旦我被更新，务必更新我的开头注释以及所属文件夹的md
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import {
  fetchPersonaV2,
  patchPersonaV2,
  startBattleFromPersona,
  type Decision,
  type EvidenceItem,
  type Expression,
  type Identity,
  type Interpersonal,
  type PersonaPatchV2,
  type PersonaV2,
} from '../services/personaV2'
import { usePersonaBuild } from '../hooks/usePersonaBuild'
import PersonaBuildProgress from '../components/PersonaBuildProgress'
import PersonaHero from '../components/persona-editor/PersonaHero'
import LayerCard, { type LayerColor } from '../components/persona-editor/LayerCard'
import FeatureRow from '../components/persona-editor/FeatureRow'
import EvidencePopover from '../components/persona-editor/EvidencePopover'
import FloatingCTA from '../components/persona-editor/FloatingCTA'
import ConfirmDialog from '../components/layout/ConfirmDialog'
import '../components/persona-editor/personaEditor.css'
import './PersonaEditorPage.css'

type LayerKey = 'hard_rules' | 'identity' | 'expression' | 'decision' | 'interpersonal'

// --- Enhancement diff helpers ---
interface DiffItem {
  type: 'added' | 'changed' | 'removed'
  layer: string
  field: string
  value: string
  oldValue?: string
}

interface EnhanceDiffSummary {
  items: DiffItem[]
  added: number
  changed: number
  removed: number
}

function diffStringArrays(
  oldArr: string[],
  newArr: string[],
  layer: string,
  field: string,
): DiffItem[] {
  const items: DiffItem[] = []
  const oldSet = new Set(oldArr)
  const newSet = new Set(newArr)
  for (const v of newArr) {
    if (!oldSet.has(v)) items.push({ type: 'added', layer, field, value: v })
  }
  for (const v of oldArr) {
    if (!newSet.has(v)) items.push({ type: 'removed', layer, field, value: v })
  }
  return items
}

function diffStringField(
  oldVal: string | null | undefined,
  newVal: string | null | undefined,
  layer: string,
  field: string,
): DiffItem | null {
  const o = oldVal || ''
  const n = newVal || ''
  if (o === n) return null
  if (!o && n) return { type: 'added', layer, field, value: n }
  if (o && !n) return { type: 'removed', layer, field, value: o }
  return { type: 'changed', layer, field, value: n, oldValue: o }
}

function computeEnhanceDiff(oldP: PersonaV2 | null, newP: PersonaV2): EnhanceDiffSummary {
  const items: DiffItem[] = []
  if (!oldP) {
    return { items: [{ type: 'added', layer: '整体', field: '画像', value: '全新创建' }], added: 1, changed: 0, removed: 0 }
  }

  // Hard rules
  const oldRules = new Set(oldP.hard_rules.map((r) => r.statement))
  const newRules = new Set(newP.hard_rules.map((r) => r.statement))
  for (const r of newP.hard_rules) {
    if (!oldRules.has(r.statement)) items.push({ type: 'added', layer: '铁律', field: `[${r.severity}]`, value: r.statement })
  }
  for (const r of oldP.hard_rules) {
    if (!newRules.has(r.statement)) items.push({ type: 'removed', layer: '铁律', field: `[${r.severity}]`, value: r.statement })
  }

  // Identity
  const oi = oldP.identity, ni = newP.identity
  if (ni) {
    const d = diffStringField(oi?.background, ni.background, '身份', '背景')
    if (d) items.push(d)
    items.push(...diffStringArrays(oi?.core_values || [], ni.core_values, '身份', '核心价值观'))
    const ha = diffStringField(oi?.hidden_agenda, ni.hidden_agenda, '身份', '隐藏议程')
    if (ha) items.push(ha)
  }

  // Expression
  const oe = oldP.expression, ne = newP.expression
  if (ne) {
    const t = diffStringField(oe?.tone, ne.tone, '表达风格', '语气')
    if (t) items.push(t)
    items.push(...diffStringArrays(oe?.catchphrases || [], ne.catchphrases, '表达风格', '口头禅'))
  }

  // Decision
  const od = oldP.decision, nd = newP.decision
  if (nd) {
    const s = diffStringField(od?.style, nd.style, '决策模式', '风格')
    if (s) items.push(s)
    const r = diffStringField(od?.risk_tolerance, nd.risk_tolerance, '决策模式', '风险偏好')
    if (r) items.push(r)
    items.push(...diffStringArrays(od?.typical_questions || [], nd.typical_questions, '决策模式', '典型追问'))
  }

  // Interpersonal
  const oip = oldP.interpersonal, nip = newP.interpersonal
  if (nip) {
    const am = diffStringField(oip?.authority_mode, nip.authority_mode, '人际风格', '权威模式')
    if (am) items.push(am)
    items.push(...diffStringArrays(oip?.triggers || [], nip.triggers, '人际风格', '触发器'))
    items.push(...diffStringArrays(oip?.emotion_states || [], nip.emotion_states, '人际风格', '情绪状态'))
  }

  return {
    items,
    added: items.filter((i) => i.type === 'added').length,
    changed: items.filter((i) => i.type === 'changed').length,
    removed: items.filter((i) => i.type === 'removed').length,
  }
}

const LAYER_META: Record<LayerKey, { title: string; emoji: string; color: LayerColor }> = {
  hard_rules:    { title: 'Hard Rules',    emoji: '⚖️', color: 'rose' },
  identity:      { title: 'Identity',      emoji: '🎯', color: 'violet' },
  expression:    { title: 'Expression',    emoji: '🗣️', color: 'green' },
  decision:      { title: 'Decision',      emoji: '🧠', color: 'amber' },
  interpersonal: { title: 'Interpersonal', emoji: '🤝', color: 'green' },
}

const LOW_CONF = 0.6

export default function PersonaEditorPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [persona, setPersona] = useState<PersonaV2 | null>(null)
  const [draft, setDraft] = useState<PersonaV2 | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [popover, setPopover] = useState<{ ev: EvidenceItem; rect: DOMRect } | null>(null)
  const [leaveConfirm, setLeaveConfirm] = useState<null | (() => void)>(null)

  // Load persona
  useEffect(() => {
    if (!id) return
    setLoading(true)
    fetchPersonaV2(id)
      .then((p) => {
        setPersona(p)
        setDraft(p)
        setError(null)
      })
      .catch((e) => setError(String(e?.message || e)))
      .finally(() => setLoading(false))
  }, [id])

  const evidenceMap = useMemo(() => {
    const m = new Map<string, EvidenceItem>()
    if (draft) for (const ev of draft.evidence) m.set(ev.claim, ev)
    return m
  }, [draft])

  const strength = useMemo(() => {
    if (!draft || draft.evidence.length === 0) return 0
    const sum = draft.evidence.reduce((s, e) => s + e.confidence, 0)
    return sum / draft.evidence.length
  }, [draft])

  const hasUnsaved = useMemo(() => {
    if (!persona || !draft) return false
    return JSON.stringify(persona) !== JSON.stringify(draft)
  }, [persona, draft])

  // beforeunload guard (AC8 partial)
  useEffect(() => {
    if (!hasUnsaved) return
    const handler = (e: BeforeUnloadEvent) => {
      e.preventDefault()
      e.returnValue = ''
    }
    window.addEventListener('beforeunload', handler)
    return () => window.removeEventListener('beforeunload', handler)
  }, [hasUnsaved])

  const showEvidence = useCallback(
    (claim: string, anchor: HTMLElement) => {
      const ev = evidenceMap.get(claim)
      if (!ev) return
      setPopover({ ev, rect: anchor.getBoundingClientRect() })
    },
    [evidenceMap],
  )

  const closePopover = useCallback(() => setPopover(null), [])

  const toggleReject = useCallback((layer: LayerKey, idx: number) => {
    setDraft((d) => {
      if (!d) return d
      const cur = new Set(d.rejected_features[layer] || [])
      if (cur.has(idx)) cur.delete(idx)
      else cur.add(idx)
      return {
        ...d,
        rejected_features: {
          ...d.rejected_features,
          [layer]: Array.from(cur).sort((a, b) => a - b),
        },
      }
    })
  }, [])

  const isRejected = (layer: LayerKey, idx: number) =>
    Boolean(draft?.rejected_features[layer]?.includes(idx))

  // ------ layer field editors ------

  const editHardRule = (idx: number, value: string) => {
    setDraft((d) => {
      if (!d) return d
      const list = [...d.hard_rules]
      list[idx] = { ...list[idx], statement: value }
      return { ...d, hard_rules: list }
    })
  }

  const editIdentity = (patch: Partial<Identity>) => {
    setDraft((d) => {
      if (!d || !d.identity) return d
      return { ...d, identity: { ...d.identity, ...patch } }
    })
  }
  const editIdentityCoreValue = (i: number, value: string) => {
    setDraft((d) => {
      if (!d || !d.identity) return d
      const core_values = [...d.identity.core_values]
      core_values[i] = value
      return { ...d, identity: { ...d.identity, core_values } }
    })
  }

  const editExpression = (patch: Partial<Expression>) => {
    setDraft((d) => {
      if (!d || !d.expression) return d
      return { ...d, expression: { ...d.expression, ...patch } }
    })
  }
  const editExpressionCatchphrase = (i: number, value: string) => {
    setDraft((d) => {
      if (!d || !d.expression) return d
      const catchphrases = [...d.expression.catchphrases]
      catchphrases[i] = value
      return { ...d, expression: { ...d.expression, catchphrases } }
    })
  }

  const editDecision = (patch: Partial<Decision>) => {
    setDraft((d) => {
      if (!d || !d.decision) return d
      return { ...d, decision: { ...d.decision, ...patch } }
    })
  }
  const editDecisionQuestion = (i: number, value: string) => {
    setDraft((d) => {
      if (!d || !d.decision) return d
      const typical_questions = [...d.decision.typical_questions]
      typical_questions[i] = value
      return { ...d, decision: { ...d.decision, typical_questions } }
    })
  }

  const editInterpersonal = (patch: Partial<Interpersonal>) => {
    setDraft((d) => {
      if (!d || !d.interpersonal) return d
      return { ...d, interpersonal: { ...d.interpersonal, ...patch } }
    })
  }
  const editInterpersonalTrigger = (i: number, value: string) => {
    setDraft((d) => {
      if (!d || !d.interpersonal) return d
      const triggers = [...d.interpersonal.triggers]
      triggers[i] = value
      return { ...d, interpersonal: { ...d.interpersonal, triggers } }
    })
  }
  const editInterpersonalEmotion = (i: number, value: string) => {
    setDraft((d) => {
      if (!d || !d.interpersonal) return d
      const emotion_states = [...d.interpersonal.emotion_states]
      emotion_states[i] = value
      return { ...d, interpersonal: { ...d.interpersonal, emotion_states } }
    })
  }

  // --- Enhancement mode ---
  const [showEnhance, setShowEnhance] = useState(false)
  const [enhanceText, setEnhanceText] = useState('')
  const enhance = usePersonaBuild()
  const enhanceTextRef = useRef('')
  const [enhanceDiff, setEnhanceDiff] = useState<EnhanceDiffSummary | null>(null)
  const pendingEnhancePersona = useRef<PersonaV2 | null>(null)

  const preEnhanceSnapshot = useRef<PersonaV2 | null>(null)

  const handleStartEnhance = () => {
    const text = enhanceText.trim()
    if (!text || !id) return
    enhanceTextRef.current = text
    // Snapshot current persona BEFORE enhancement starts
    preEnhanceSnapshot.current = persona ? { ...persona } : null
    enhance.start({
      materials: [text],
      target_persona_id: id,
    })
  }

  // When enhancement finishes (done or error with potential partial success), show diff
  const prevEnhanceStatus = useRef(enhance.status)
  useEffect(() => {
    const prev = prevEnhanceStatus.current
    prevEnhanceStatus.current = enhance.status
    // Only trigger on transition INTO done/error from running
    if (prev !== 'running') return
    if (enhance.status !== 'done' && enhance.status !== 'error') return
    if (!id) return
    // Backend may have persisted even if SSE stream closed early — always try to fetch
    fetchPersonaV2(id)
      .then((newP) => {
        const baseline = preEnhanceSnapshot.current || persona
        const diff = computeEnhanceDiff(baseline, newP)
        // Always set the new persona and show dialog
        pendingEnhancePersona.current = newP
        setEnhanceDiff(diff)
      })
      .catch(() => {
        // Fetch failed — show empty diff so user at least gets feedback
        setEnhanceDiff({ items: [], added: 0, changed: 0, removed: 0 })
      })
  }, [enhance.status, id]) // eslint-disable-line react-hooks/exhaustive-deps

  const handleAcceptEnhance = () => {
    const newP = pendingEnhancePersona.current
    if (newP) {
      setPersona(newP)
      setDraft(newP)
    }
    setEnhanceDiff(null)
    pendingEnhancePersona.current = null
    preEnhanceSnapshot.current = null
    setShowEnhance(false)
    setEnhanceText('')
    enhance.reset()
  }

  const handleRejectEnhance = () => {
    setEnhanceDiff(null)
    pendingEnhancePersona.current = null
    preEnhanceSnapshot.current = null
    enhance.reset()
  }

  const handleSave = async () => {
    if (!draft || !id) return
    setSaving(true)
    setSaveError(null)
    try {
      const body: PersonaPatchV2 = {
        name: draft.name,
        role: draft.role,
        avatar_color: draft.avatar_color || undefined,
        hard_rules: draft.hard_rules,
        identity: draft.identity || undefined,
        expression: draft.expression || undefined,
        decision: draft.decision || undefined,
        interpersonal: draft.interpersonal || undefined,
        user_context: draft.user_context || undefined,
        rejected_features: draft.rejected_features,
      }
      const updated = await patchPersonaV2(id, body)
      setPersona(updated)
      setDraft(updated)
    } catch (e: unknown) {
      const msg = (e as Error)?.message || String(e)
      setSaveError(msg)
    } finally {
      setSaving(false)
    }
  }

  const doStartBattle = async () => {
    if (!id) return
    try {
      const room = await startBattleFromPersona(id)
      navigate(`/chat/${room.id}`)
    } catch (e: unknown) {
      const msg = (e as Error)?.message || String(e)
      setSaveError(`开演练失败：${msg}`)
    }
  }

  const handleStartBattle = () => {
    // Story 2.8: real chatroom wiring. When there are unsaved edits we ask
    // the user first — they can discard changes and go, or cancel to save.
    if (hasUnsaved) {
      setLeaveConfirm(() => () => {
        void doStartBattle()
      })
      return
    }
    void doStartBattle()
  }

  if (loading) return <div className="editor-status">加载中…</div>
  if (error || !draft) {
    return (
      <div className="editor-status error">
        <p>加载失败：{error || 'persona 不存在'}</p>
        <button type="button" onClick={() => navigate('/settings')}>
          返回 Settings
        </button>
      </div>
    )
  }

  // ======== 渲染 5-layer 列表 ========

  // Hard Rules
  const hardRulesRows = draft.hard_rules.map((r, idx) => {
    const ev = evidenceMap.get(r.statement)
    return (
      <FeatureRow
        key={`hr-${idx}`}
        emoji="⚖️"
        text={r.statement}
        rejected={isRejected('hard_rules', idx)}
        lowConfidence={ev ? ev.confidence < LOW_CONF : false}
        evidenceFocused={popover?.ev.claim === r.statement}
        onChange={(v) => editHardRule(idx, v)}
        onShowEvidence={ev ? (a) => showEvidence(r.statement, a) : undefined}
        onReject={() => toggleReject('hard_rules', idx)}
      />
    )
  })

  // Identity
  const identityRows: React.ReactNode[] = []
  if (draft.identity) {
    const id0 = draft.identity
    if (id0.background) {
      identityRows.push(
        <FeatureRow
          key="id-bg"
          emoji="🎯"
          text={id0.background}
          onChange={(v) => editIdentity({ background: v })}
        />,
      )
    }
    id0.core_values.forEach((cv, i) =>
      identityRows.push(
        <FeatureRow
          key={`id-cv-${i}`}
          emoji="✦"
          text={cv}
          onChange={(v) => editIdentityCoreValue(i, v)}
        />,
      ),
    )
    if (id0.hidden_agenda) {
      identityRows.push(
        <FeatureRow
          key="id-ha"
          emoji="🕶️"
          text={`隐藏议程：${id0.hidden_agenda}`}
          onChange={(v) =>
            editIdentity({ hidden_agenda: v.replace(/^隐藏议程[：:]\s*/, '') })
          }
        />,
      )
    }
    if (id0.information_preference) {
      identityRows.push(
        <FeatureRow
          key="id-ip"
          emoji="📋"
          text={`信息偏好：${id0.information_preference}`}
          onChange={(v) =>
            editIdentity({ information_preference: v.replace(/^信息偏好[：:]\s*/, '') })
          }
        />,
      )
    }
  }

  // Expression
  const exprRows: React.ReactNode[] = []
  if (draft.expression) {
    const ex = draft.expression
    if (ex.tone) {
      exprRows.push(
        <FeatureRow
          key="ex-tone"
          emoji="🗣️"
          text={`语气：${ex.tone}`}
          onChange={(v) => editExpression({ tone: v.replace(/^语气[：:]\s*/, '') })}
        />,
      )
    }
    ex.catchphrases.forEach((p, i) =>
      exprRows.push(
        <FeatureRow
          key={`ex-cp-${i}`}
          emoji="💬"
          text={p}
          onChange={(v) => editExpressionCatchphrase(i, v)}
        />,
      ),
    )
    exprRows.push(
      <FeatureRow
        key="ex-int"
        emoji="✋"
        text={`打断倾向：${ex.interruption_tendency}`}
        onChange={(v) =>
          editExpression({
            interruption_tendency: v.replace(/^打断倾向[：:]\s*/, ''),
          })
        }
      />,
    )
  }

  // Decision
  const decRows: React.ReactNode[] = []
  if (draft.decision) {
    const dc = draft.decision
    if (dc.style) {
      decRows.push(
        <FeatureRow
          key="dc-style"
          emoji="🧠"
          text={`决策风格：${dc.style}`}
          onChange={(v) => editDecision({ style: v.replace(/^决策风格[：:]\s*/, '') })}
        />,
      )
    }
    decRows.push(
      <FeatureRow
        key="dc-rt"
        emoji="⚠️"
        text={`风险容忍：${dc.risk_tolerance}`}
        onChange={(v) =>
          editDecision({ risk_tolerance: v.replace(/^风险容忍[：:]\s*/, '') })
        }
      />,
    )
    dc.typical_questions.forEach((q, i) =>
      decRows.push(
        <FeatureRow
          key={`dc-tq-${i}`}
          emoji="❓"
          text={q}
          onChange={(v) => editDecisionQuestion(i, v)}
        />,
      ),
    )
  }

  // Interpersonal
  const ipRows: React.ReactNode[] = []
  if (draft.interpersonal) {
    const ip = draft.interpersonal
    if (ip.authority_mode) {
      ipRows.push(
        <FeatureRow
          key="ip-am"
          emoji="🤝"
          text={`权威模式：${ip.authority_mode}`}
          onChange={(v) =>
            editInterpersonal({ authority_mode: v.replace(/^权威模式[：:]\s*/, '') })
          }
        />,
      )
    }
    ip.triggers.forEach((t, i) =>
      ipRows.push(
        <FeatureRow
          key={`ip-tr-${i}`}
          emoji="⚡"
          text={t}
          onChange={(v) => editInterpersonalTrigger(i, v)}
        />,
      ),
    )
    ip.emotion_states.forEach((s, i) =>
      ipRows.push(
        <FeatureRow
          key={`ip-es-${i}`}
          emoji="😤"
          text={s}
          onChange={(v) => editInterpersonalEmotion(i, v)}
        />,
      ),
    )
    if (ip.escalation_chains && ip.escalation_chains.length > 0) {
      ip.escalation_chains.forEach((chain, ci) => {
        const stepsStr = chain.steps.join(' → ')
        ipRows.push(
          <FeatureRow
            key={`ip-ec-${ci}`}
            emoji="🔺"
            text={`升级链：${chain.trigger} → ${stepsStr}`}
            onChange={() => {}}
          />,
        )
      })
    }
  }

  const emptyLayerNotice = (
    <div className="layer-empty">暂无内容（可通过 Story 2.6 的生成器补充）</div>
  )

  return (
    <div className="persona-editor">
      <PersonaHero
        persona={draft}
        strength={strength}
        evidenceCount={draft.evidence.length}
        materialCount={draft.source_materials.length}
      />

      <LayerCard
        title={LAYER_META.hard_rules.title}
        emoji={LAYER_META.hard_rules.emoji}
        color={LAYER_META.hard_rules.color}
        count={hardRulesRows.length}
      >
        {hardRulesRows.length ? hardRulesRows : emptyLayerNotice}
      </LayerCard>

      <LayerCard
        title={LAYER_META.identity.title}
        emoji={LAYER_META.identity.emoji}
        color={LAYER_META.identity.color}
        count={identityRows.length}
      >
        {identityRows.length ? identityRows : emptyLayerNotice}
      </LayerCard>

      <LayerCard
        title={LAYER_META.expression.title}
        emoji={LAYER_META.expression.emoji}
        color={LAYER_META.expression.color}
        count={exprRows.length}
      >
        {exprRows.length ? exprRows : emptyLayerNotice}
      </LayerCard>

      <LayerCard
        title={LAYER_META.decision.title}
        emoji={LAYER_META.decision.emoji}
        color={LAYER_META.decision.color}
        count={decRows.length}
      >
        {decRows.length ? decRows : emptyLayerNotice}
      </LayerCard>

      <LayerCard
        title={LAYER_META.interpersonal.title}
        emoji={LAYER_META.interpersonal.emoji}
        color={LAYER_META.interpersonal.color}
        count={ipRows.length}
      >
        {ipRows.length ? ipRows : emptyLayerNotice}
      </LayerCard>

      {saveError && (
        <div className="editor-save-error">
          保存失败：{saveError}
        </div>
      )}

      {/* User context — relationship to current user */}
      <div className="user-context-section">
        <h3>与当前对话者的关系</h3>
        <p className="user-context-hint">描述这个角色对你的期待、你们的汇报关系、他关心你负责的哪些领域</p>
        <textarea
          className="user-context-textarea"
          value={draft.user_context || ''}
          onChange={(e) => setDraft((d) => d ? { ...d, user_context: e.target.value || null } : d)}
          placeholder="例：我是万华，FDE质量体系负责人。他期望我负责评价体系和测试集构建，交付物要经得起推敲。会直接点名确认我是否理解。"
          rows={4}
        />
      </div>

      <EvidencePopover
        evidence={popover?.ev || null}
        anchor={popover?.rect || null}
        onClose={closePopover}
      />

      {/* Enhancement panel */}
      {showEnhance && (
        <div className="enhance-panel">
          <h3>追加素材增强画像</h3>
          <textarea
            className="enhance-textarea"
            value={enhanceText}
            onChange={(e) => setEnhanceText(e.target.value)}
            placeholder="粘贴新的聊天记录 / 邮件 / 会议纪要，AI 会将新发现的特征合并到现有画像中…"
            rows={6}
            disabled={enhance.status === 'running'}
          />
          {enhance.status === 'running' && (
            <PersonaBuildProgress events={enhance.events} status={enhance.status} error={enhance.error} />
          )}
          <div className="enhance-actions">
            <button
              type="button"
              className="btn-primary"
              onClick={handleStartEnhance}
              disabled={!enhanceText.trim() || enhance.status === 'running'}
            >
              {enhance.status === 'running' ? '增强中…' : '开始增强'}
            </button>
            <button
              type="button"
              className="btn-ghost"
              onClick={() => { setShowEnhance(false); setEnhanceText(''); enhance.reset() }}
              disabled={enhance.status === 'running'}
            >
              取消
            </button>
          </div>
        </div>
      )}

      {/* Enhancement diff summary dialog */}
      {enhanceDiff && (
        <div className="dialog-overlay" onClick={handleRejectEnhance}>
          <div className="dialog enhance-diff-dialog" onClick={(e) => e.stopPropagation()}>
            <h3>增强完成 — 变更摘要</h3>
            <div className="enhance-diff-stats">
              {enhanceDiff.added > 0 && <span className="diff-badge diff-added">+{enhanceDiff.added} 新增</span>}
              {enhanceDiff.changed > 0 && <span className="diff-badge diff-changed">{enhanceDiff.changed} 修改</span>}
              {enhanceDiff.removed > 0 && <span className="diff-badge diff-removed">-{enhanceDiff.removed} 移除</span>}
              {enhanceDiff.items.length === 0 && <span className="diff-badge">无变化</span>}
            </div>
            {enhanceDiff.items.length > 0 ? (
              <div className="enhance-diff-list">
                {enhanceDiff.items.map((item, i) => (
                  <div key={i} className={`enhance-diff-item diff-${item.type}`}>
                    <span className="diff-type-tag">
                      {item.type === 'added' ? '新增' : item.type === 'changed' ? '修改' : '移除'}
                    </span>
                    <span className="diff-layer">{item.layer}</span>
                    <span className="diff-field">{item.field}</span>
                    <span className="diff-value">{item.value}</span>
                  </div>
                ))}
              </div>
            ) : (
              <div className="enhance-diff-empty">
                AI 已处理素材，但未检测到新的特征变化。可能素材中的信息已在现有画像中体现。
              </div>
            )}
            <div className="enhance-diff-actions">
              <button type="button" className="btn-primary" onClick={handleAcceptEnhance}>
                {enhanceDiff.items.length > 0 ? '应用变更' : '确定'}
              </button>
              {enhanceDiff.items.length > 0 && (
                <button type="button" className="btn-ghost" onClick={handleRejectEnhance}>
                  放弃
                </button>
              )}
            </div>
          </div>
        </div>
      )}

      <FloatingCTA
        hasUnsaved={hasUnsaved}
        saving={saving}
        onSave={handleSave}
        onStartBattle={handleStartBattle}
        onEnhance={() => setShowEnhance(true)}
        showEnhance={!showEnhance}
      />

      <ConfirmDialog
        open={Boolean(leaveConfirm)}
        title="有未保存修改"
        message="离开会丢失未保存的修改，确定离开？"
        confirmLabel="离开"
        cancelLabel="留下"
        danger
        onConfirm={() => {
          leaveConfirm?.()
          setLeaveConfirm(null)
        }}
        onCancel={() => setLeaveConfirm(null)}
      />
    </div>
  )
}
