// input: route /persona/:id/edit
// output: 完整编辑器 (Hero + 5 LayerCards + EvidencePopover + FloatingCTA + 未保存离开确认)
// owner: wanhua.gu
// pos: 表示层 - 5-layer persona 编辑器主页 (Story 2.7)；一旦我被更新，务必更新我的开头注释以及所属文件夹的md
import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import {
  fetchPersonaV2,
  patchPersonaV2,
  type Decision,
  type EvidenceItem,
  type Expression,
  type Identity,
  type Interpersonal,
  type PersonaPatchV2,
  type PersonaV2,
} from '../services/personaV2'
import PersonaHero from '../components/persona-editor/PersonaHero'
import LayerCard, { type LayerColor } from '../components/persona-editor/LayerCard'
import FeatureRow from '../components/persona-editor/FeatureRow'
import EvidencePopover from '../components/persona-editor/EvidencePopover'
import FloatingCTA from '../components/persona-editor/FloatingCTA'
import ConfirmDialog from '../components/layout/ConfirmDialog'
import '../components/persona-editor/personaEditor.css'
import './PersonaEditorPage.css'

type LayerKey = 'hard_rules' | 'identity' | 'expression' | 'decision' | 'interpersonal'

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

  const handleStartBattle = () => {
    // Story 2.8 will wire battle_prep_service.create_room_from_persona
    if (hasUnsaved) {
      setLeaveConfirm(() => () => {
        window.alert('演练接入即将在 Story 2.8 上线（将带上该画像进入聊天室）')
        navigate('/chat')
      })
      return
    }
    window.alert('演练接入即将在 Story 2.8 上线（将带上该画像进入聊天室）')
    navigate('/chat')
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

      <EvidencePopover
        evidence={popover?.ev || null}
        anchor={popover?.rect || null}
        onClose={closePopover}
      />

      <FloatingCTA
        hasUnsaved={hasUnsaved}
        saving={saving}
        onSave={handleSave}
        onStartBattle={handleStartBattle}
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
