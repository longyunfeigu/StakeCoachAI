// input: persona id (route 参数) + patch payload
// output: fetchPersonaV2 / patchPersonaV2 — 编辑器数据访问层 (Story 2.7)
// owner: wanhua.gu
// pos: 表示层 - persona v2 GET/PATCH HTTP client；一旦我被更新，务必更新我的开头注释以及所属文件夹的md

const API_BASE = '/api/v1/stakeholder'

export interface HardRule {
  statement: string
  severity: string
}

export interface Identity {
  background: string
  core_values: string[]
  hidden_agenda: string | null
  information_preference: string | null
}

export interface Expression {
  tone: string
  catchphrases: string[]
  interruption_tendency: string
}

export interface Decision {
  style: string
  risk_tolerance: string
  typical_questions: string[]
}

export interface EscalationChain {
  trigger: string
  steps: string[]
}

export interface Interpersonal {
  authority_mode: string
  triggers: string[]
  emotion_states: string[]
  escalation_chains: EscalationChain[]
}

export interface EvidenceItem {
  claim: string
  citations: string[]
  confidence: number
  source_material_id: string
  layer: string
}

export interface PersonaV2 {
  id: string
  name: string
  role: string
  avatar_color: string | null
  schema_version: number
  hard_rules: HardRule[]
  identity: Identity | null
  expression: Expression | null
  decision: Decision | null
  interpersonal: Interpersonal | null
  user_context: string | null
  evidence: EvidenceItem[]
  rejected_features: Record<string, number[]>
  source_materials: string[]
}

export interface PersonaPatchV2 {
  name?: string
  role?: string
  avatar_color?: string
  hard_rules?: HardRule[]
  identity?: Identity
  expression?: Expression
  decision?: Decision
  interpersonal?: Interpersonal
  user_context?: string
  rejected_features?: Record<string, number[]>
}

interface ApiResp<T> {
  code: number
  message: string
  data: T
}

export async function fetchPersonaV2(id: string): Promise<PersonaV2> {
  const resp = await fetch(`${API_BASE}/personas/${id}/v2`)
  if (!resp.ok) {
    const err = await resp.json().catch(() => null)
    throw new Error(err?.error?.message || `Failed to load persona: ${resp.status}`)
  }
  const json: ApiResp<PersonaV2> = await resp.json()
  return json.data
}

export async function patchPersonaV2(
  id: string,
  body: PersonaPatchV2,
): Promise<PersonaV2> {
  const resp = await fetch(`${API_BASE}/personas/${id}/v2`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!resp.ok) {
    const err = await resp.json().catch(() => null)
    throw new Error(
      err?.error?.message || err?.detail?.message || `Failed to save persona: ${resp.status}`,
    )
  }
  const json: ApiResp<PersonaV2> = await resp.json()
  return json.data
}

// ---------------------------------------------------------------------------
// Story 2.8 — Start battle from existing persona
// ---------------------------------------------------------------------------

export interface StartBattleResponse {
  id: number
  name: string
  type: string
  persona_ids: string[]
}

export async function startBattleFromPersona(
  id: string,
): Promise<StartBattleResponse> {
  const resp = await fetch(`${API_BASE}/personas/${id}/start-battle`, {
    method: 'POST',
  })
  if (!resp.ok) {
    const err = await resp.json().catch(() => null)
    throw new Error(
      err?.error?.message || err?.detail || `Failed to start battle: ${resp.status}`,
    )
  }
  const json: ApiResp<StartBattleResponse> = await resp.json()
  return json.data
}
