const API_BASE = '/api/v1/stakeholder'

export interface PersonaSummary {
  id: string
  name: string
  role: string
  avatar_color: string | null
  organization_id: number | null
  team_id: number | null
  parse_status: string
}

export interface PersonaDetail extends PersonaSummary {
  profile_summary: string
  content: string
}

export interface ChatRoom {
  id: number
  name: string
  type: 'private' | 'group' | 'battle_prep'
  persona_ids: string[]
  created_at: string | null
  last_message_at: string | null
}

export interface Message {
  id: number
  room_id: number
  sender_type: 'user' | 'persona' | 'system'
  sender_id: string
  content: string
  timestamp: string | null
  emotion_score: number | null
  emotion_label: string | null
}

export interface ChatRoomDetail {
  room: ChatRoom
  messages: Message[]
}

interface ApiResponse<T> {
  code: number
  message: string
  data: T
}

// ---------------------------------------------------------------------------
// Dispatcher transparency types (SSE round_end payload)
// ---------------------------------------------------------------------------

export interface DispatchEntry {
  persona_id: string
  reason: string
}

export interface DispatchPhase {
  phase: 'initial' | 'followup'
  responders: DispatchEntry[]
  trigger_persona_id?: string
}

export interface RoundEndData {
  dispatch_log?: DispatchPhase[]
  total_replies?: number
  max_rounds_reached?: boolean
}

export async function fetchPersonas(): Promise<PersonaSummary[]> {
  const resp = await fetch(`${API_BASE}/personas`)
  if (!resp.ok) throw new Error(`Failed to fetch personas: ${resp.status}`)
  const json: ApiResponse<PersonaSummary[]> = await resp.json()
  return json.data
}

export async function fetchPersonaDetail(id: string): Promise<PersonaDetail> {
  const resp = await fetch(`${API_BASE}/personas/${id}`)
  if (!resp.ok) throw new Error(`Failed to fetch persona: ${resp.status}`)
  const json: ApiResponse<PersonaDetail> = await resp.json()
  return json.data
}

export async function fetchRooms(): Promise<ChatRoom[]> {
  const resp = await fetch(`${API_BASE}/rooms`)
  if (!resp.ok) throw new Error(`Failed to fetch rooms: ${resp.status}`)
  const json: ApiResponse<ChatRoom[]> = await resp.json()
  return json.data
}

export async function fetchRoomDetail(roomId: number): Promise<ChatRoomDetail> {
  const resp = await fetch(`${API_BASE}/rooms/${roomId}`)
  if (!resp.ok) throw new Error(`Failed to fetch room: ${resp.status}`)
  const json: ApiResponse<ChatRoomDetail> = await resp.json()
  return json.data
}

export async function sendMessage(roomId: number, content: string): Promise<Message> {
  const resp = await fetch(`${API_BASE}/rooms/${roomId}/messages`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ content }),
  })
  if (!resp.ok) throw new Error(`Failed to send message: ${resp.status}`)
  const json: ApiResponse<Message> = await resp.json()
  return json.data
}

async function downloadBlob(resp: globalThis.Response, fallback: string): Promise<void> {
  const blob = await resp.blob()
  const disposition = resp.headers.get('Content-Disposition') || ''
  const match = disposition.match(/filename\*?="?(?:UTF-8'')?(.+?)"?$/)
  const filename = match?.[1] ? decodeURIComponent(match[1]) : fallback
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

export async function exportRoom(roomId: number): Promise<void> {
  const resp = await fetch(`${API_BASE}/rooms/${roomId}/export`)
  if (!resp.ok) throw new Error(`Failed to export: ${resp.status}`)
  await downloadBlob(resp, `chat-export-${roomId}.md`)
}

export async function exportRoomHtml(roomId: number): Promise<void> {
  const resp = await fetch(`${API_BASE}/rooms/${roomId}/export/html`)
  if (!resp.ok) throw new Error(`Failed to export: ${resp.status}`)
  await downloadBlob(resp, `chat-export-${roomId}.html`)
}

export async function deleteRoom(roomId: number): Promise<void> {
  const resp = await fetch(`${API_BASE}/rooms/${roomId}`, { method: 'DELETE' })
  if (!resp.ok) throw new Error(`Failed to delete room: ${resp.status}`)
}

export async function createRoom(data: {
  name: string
  type: 'private' | 'group'
  persona_ids: string[]
  scenario_id?: number
}): Promise<ChatRoom> {
  const resp = await fetch(`${API_BASE}/rooms`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!resp.ok) {
    const err = await resp.json().catch(() => null)
    throw new Error(err?.error?.details || `Failed to create room: ${resp.status}`)
  }
  const json: ApiResponse<ChatRoom> = await resp.json()
  return json.data
}

// ---------------------------------------------------------------------------
// Persona CRUD (Feature 5)
// ---------------------------------------------------------------------------

export async function createPersona(data: {
  id: string
  name: string
  role: string
  avatar_color: string
  content: string
  organization_id?: number | null
  team_id?: number | null
}): Promise<void> {
  const resp = await fetch(`${API_BASE}/personas`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!resp.ok) {
    const err = await resp.json().catch(() => null)
    throw new Error(err?.error?.details || `Failed to create persona: ${resp.status}`)
  }
}

export async function updatePersona(
  id: string,
  data: { name?: string; role?: string; avatar_color?: string; content?: string; organization_id?: number | null; team_id?: number | null },
): Promise<void> {
  const resp = await fetch(`${API_BASE}/personas/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!resp.ok) throw new Error(`Failed to update persona: ${resp.status}`)
}

export async function deletePersona(id: string): Promise<void> {
  const resp = await fetch(`${API_BASE}/personas/${id}`, { method: 'DELETE' })
  if (!resp.ok) throw new Error(`Failed to delete persona: ${resp.status}`)
}

// ---------------------------------------------------------------------------
// Scenario CRUD (Feature 6)
// ---------------------------------------------------------------------------

export interface Scenario {
  id: number
  name: string
  description: string
  context_prompt: string
  suggested_persona_ids: string[]
  created_at: string | null
}

export async function fetchScenarios(): Promise<Scenario[]> {
  const resp = await fetch(`${API_BASE}/scenarios`)
  if (!resp.ok) throw new Error(`Failed to fetch scenarios: ${resp.status}`)
  const json: ApiResponse<Scenario[]> = await resp.json()
  return json.data
}

export async function createScenario(data: {
  name: string
  description?: string
  context_prompt: string
  suggested_persona_ids?: string[]
}): Promise<Scenario> {
  const resp = await fetch(`${API_BASE}/scenarios`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!resp.ok) throw new Error(`Failed to create scenario: ${resp.status}`)
  const json: ApiResponse<Scenario> = await resp.json()
  return json.data
}

export async function updateScenario(
  id: number,
  data: { name?: string; description?: string; context_prompt?: string; suggested_persona_ids?: string[] },
): Promise<void> {
  const resp = await fetch(`${API_BASE}/scenarios/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!resp.ok) throw new Error(`Failed to update scenario: ${resp.status}`)
}

export async function deleteScenario(id: number): Promise<void> {
  const resp = await fetch(`${API_BASE}/scenarios/${id}`, { method: 'DELETE' })
  if (!resp.ok) throw new Error(`Failed to delete scenario: ${resp.status}`)
}

// ---------------------------------------------------------------------------
// Coaching types & API
// ---------------------------------------------------------------------------

export interface CoachingMessageItem {
  id: number
  session_id: number
  role: 'user' | 'coach'
  content: string
  created_at: string | null
}

export interface CoachingSession {
  id: number
  room_id: number
  report_id: number
  status: 'active' | 'completed'
  messages: CoachingMessageItem[]
  created_at: string | null
  completed_at: string | null
}

export interface CoachingSessionSummary {
  id: number
  room_id: number
  report_id: number
  status: string
  created_at: string | null
}

export async function fetchCoachingSessions(roomId: number): Promise<CoachingSessionSummary[]> {
  const resp = await fetch(`${API_BASE}/rooms/${roomId}/coaching`)
  if (!resp.ok) throw new Error(`Failed to fetch coaching sessions: ${resp.status}`)
  const json: ApiResponse<CoachingSessionSummary[]> = await resp.json()
  return json.data
}

export async function fetchCoachingSession(roomId: number, sessionId: number): Promise<CoachingSession> {
  const resp = await fetch(`${API_BASE}/rooms/${roomId}/coaching/${sessionId}`)
  if (!resp.ok) throw new Error(`Failed to fetch coaching session: ${resp.status}`)
  const json: ApiResponse<CoachingSession> = await resp.json()
  return json.data
}

export interface AnalysisReportSummary {
  id: number
  room_id: number
  summary: string
  created_at: string | null
}

export async function listAnalysisReports(roomId: number): Promise<AnalysisReportSummary[]> {
  const resp = await fetch(`${API_BASE}/rooms/${roomId}/analysis`)
  if (!resp.ok) throw new Error(`Failed to list analysis reports: ${resp.status}`)
  const json: ApiResponse<AnalysisReportSummary[]> = await resp.json()
  return json.data
}

export async function fetchAnalysisReport(roomId: number, reportId: number): Promise<AnalysisReport> {
  const resp = await fetch(`${API_BASE}/rooms/${roomId}/analysis/${reportId}`)
  if (!resp.ok) throw new Error(`Failed to fetch analysis report: ${resp.status}`)
  const json: ApiResponse<AnalysisReport> = await resp.json()
  return json.data
}

export interface ResistanceItem {
  persona_id: string
  persona_name: string
  score: number
  reason: string
  message_indices?: number[]
}

export interface ArgumentItem {
  argument: string
  target_persona: string
  effectiveness: string
  message_indices?: number[]
}

export interface SuggestionItem {
  persona_id: string
  persona_name: string
  suggestion: string
  priority: string
}

export interface AnalysisReport {
  id: number
  room_id: number
  summary: string
  content: {
    resistance_ranking: ResistanceItem[]
    effective_arguments: ArgumentItem[]
    communication_suggestions: SuggestionItem[]
    message_id_map?: Record<string, number>
  }
  created_at: string | null
}

export async function createAnalysisReport(roomId: number): Promise<AnalysisReport> {
  const resp = await fetch(`${API_BASE}/rooms/${roomId}/analysis`, { method: 'POST' })
  if (!resp.ok) {
    const json = await resp.json().catch(() => null)
    throw new Error(json?.message || `Failed to create analysis report: ${resp.status}`)
  }
  const json: ApiResponse<AnalysisReport> = await resp.json()
  return json.data
}

export function startCoachingStream(roomId: number, reportId: number): Response | Promise<Response> {
  return fetch(`${API_BASE}/rooms/${roomId}/analysis/${reportId}/coaching`, { method: 'POST' })
}

export function sendCoachingMessageStream(roomId: number, sessionId: number, content: string): Response | Promise<Response> {
  return fetch(`${API_BASE}/rooms/${roomId}/coaching/${sessionId}/messages`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ content }),
  })
}

// ---------------------------------------------------------------------------
// Live coaching (stateless, mid-conversation advice)
// ---------------------------------------------------------------------------

export function startLiveCoaching(roomId: number): Promise<Response> {
  return fetch(`${API_BASE}/rooms/${roomId}/coaching/live`, { method: 'POST' })
}

export function sendLiveCoachingMessage(
  roomId: number,
  history: { role: string; content: string }[],
  content: string,
): Promise<Response> {
  return fetch(`${API_BASE}/rooms/${roomId}/coaching/live/reply`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ history, content }),
  })
}

// ---------------------------------------------------------------------------
// Organization types & API
// ---------------------------------------------------------------------------

export interface Organization {
  id: number
  name: string
  industry: string
  description: string
  context_prompt: string
  created_at: string | null
}

export interface OrganizationDetail {
  organization: Organization
  teams: Team[]
}

export interface Team {
  id: number
  organization_id: number
  name: string
  description: string
  created_at: string | null
}

export interface PersonaRelationship {
  id: number
  organization_id: number
  from_persona_id: string
  to_persona_id: string
  relationship_type: 'superior' | 'subordinate' | 'peer' | 'cross_department'
  description: string
  created_at: string | null
}

export async function fetchOrganizations(): Promise<Organization[]> {
  const resp = await fetch(`${API_BASE}/organizations`)
  if (!resp.ok) throw new Error(`Failed to fetch organizations: ${resp.status}`)
  const json: ApiResponse<Organization[]> = await resp.json()
  return json.data
}

export async function fetchOrganizationDetail(orgId: number): Promise<OrganizationDetail> {
  const resp = await fetch(`${API_BASE}/organizations/${orgId}`)
  if (!resp.ok) throw new Error(`Failed to fetch organization: ${resp.status}`)
  const json: ApiResponse<OrganizationDetail> = await resp.json()
  return json.data
}

export async function createOrganization(data: { name: string; industry?: string; description?: string; context_prompt?: string }): Promise<Organization> {
  const resp = await fetch(`${API_BASE}/organizations`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!resp.ok) throw new Error(`Failed to create organization: ${resp.status}`)
  const json: ApiResponse<Organization> = await resp.json()
  return json.data
}

export async function updateOrganization(orgId: number, data: Partial<Pick<Organization, 'name' | 'industry' | 'description' | 'context_prompt'>>): Promise<void> {
  const resp = await fetch(`${API_BASE}/organizations/${orgId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!resp.ok) throw new Error(`Failed to update organization: ${resp.status}`)
}

export async function deleteOrganization(orgId: number): Promise<void> {
  const resp = await fetch(`${API_BASE}/organizations/${orgId}`, { method: 'DELETE' })
  if (!resp.ok) throw new Error(`Failed to delete organization: ${resp.status}`)
}

export async function fetchTeams(orgId: number): Promise<Team[]> {
  const resp = await fetch(`${API_BASE}/organizations/${orgId}/teams`)
  if (!resp.ok) throw new Error(`Failed to fetch teams: ${resp.status}`)
  const json: ApiResponse<Team[]> = await resp.json()
  return json.data
}

export async function createTeam(orgId: number, data: { name: string; description?: string }): Promise<Team> {
  const resp = await fetch(`${API_BASE}/organizations/${orgId}/teams`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!resp.ok) throw new Error(`Failed to create team: ${resp.status}`)
  const json: ApiResponse<Team> = await resp.json()
  return json.data
}

export async function deleteTeam(orgId: number, teamId: number): Promise<void> {
  const resp = await fetch(`${API_BASE}/organizations/${orgId}/teams/${teamId}`, { method: 'DELETE' })
  if (!resp.ok) throw new Error(`Failed to delete team: ${resp.status}`)
}

export async function fetchRelationships(orgId: number): Promise<PersonaRelationship[]> {
  const resp = await fetch(`${API_BASE}/organizations/${orgId}/relationships`)
  if (!resp.ok) throw new Error(`Failed to fetch relationships: ${resp.status}`)
  const json: ApiResponse<PersonaRelationship[]> = await resp.json()
  return json.data
}

export async function createRelationship(orgId: number, data: {
  from_persona_id: string
  to_persona_id: string
  relationship_type: string
  description?: string
}): Promise<PersonaRelationship> {
  const resp = await fetch(`${API_BASE}/organizations/${orgId}/relationships`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!resp.ok) throw new Error(`Failed to create relationship: ${resp.status}`)
  const json: ApiResponse<PersonaRelationship> = await resp.json()
  return json.data
}

export async function deleteRelationship(orgId: number, relId: number): Promise<void> {
  const resp = await fetch(`${API_BASE}/organizations/${orgId}/relationships/${relId}`, { method: 'DELETE' })
  if (!resp.ok) throw new Error(`Failed to delete relationship: ${resp.status}`)
}

// ---------------------------------------------------------------------------
// Growth Dashboard
// ---------------------------------------------------------------------------

export interface DimensionScore {
  score: number
  evidence: string
  suggestion: string
}

export interface CompetencyEvaluation {
  id: number
  report_id: number
  room_id: number
  room_name: string
  scores: Record<string, DimensionScore>
  overall_score: number
  created_at: string | null
}

export interface GrowthDashboard {
  overview: {
    total_sessions: number
    total_evaluations: number
    avg_overall_score: number
    latest_score: number
  }
  evaluations: CompetencyEvaluation[]
  dimension_trends: Record<string, { date: string | null; score: number }[]>
}

export async function fetchGrowthDashboard(): Promise<GrowthDashboard> {
  const resp = await fetch(`${API_BASE}/growth/dashboard`)
  if (!resp.ok) throw new Error(`Failed to fetch growth dashboard: ${resp.status}`)
  const json: ApiResponse<GrowthDashboard> = await resp.json()
  return json.data
}

export async function generateGrowthInsight(): Promise<string> {
  const resp = await fetch(`${API_BASE}/growth/insight`, { method: 'POST' })
  if (!resp.ok) throw new Error(`Failed to generate growth insight: ${resp.status}`)
  const json: ApiResponse<{ insight: string }> = await resp.json()
  return json.data.insight
}

// ---------------------------------------------------------------------------
// Battle Prep
// ---------------------------------------------------------------------------

export interface BattlePrepResult {
  persona_name: string
  persona_role: string
  persona_style: string
  scenario_context: string
  training_points: string[]
}

export interface TacticItem {
  situation: string
  response: string
}

export interface CheatSheet {
  opening: string
  key_tactics: TacticItem[]
  pitfalls: string[]
  bottom_line: string
}

export async function generateBattlePrep(description: string): Promise<BattlePrepResult> {
  const resp = await fetch(`${API_BASE}/battle-prep/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ description }),
  })
  if (!resp.ok) {
    const json = await resp.json().catch(() => null)
    throw new Error(json?.message || `生成失败: ${resp.status}`)
  }
  const json: ApiResponse<BattlePrepResult> = await resp.json()
  return json.data
}

export async function startBattle(data: {
  persona_name: string
  persona_role: string
  persona_style: string
  scenario_context: string
  selected_training_points: string[]
  difficulty: 'easy' | 'normal' | 'hard'
}): Promise<ChatRoom> {
  const resp = await fetch(`${API_BASE}/battle-prep/start`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!resp.ok) throw new Error(`Failed to start battle: ${resp.status}`)
  const json: ApiResponse<ChatRoom> = await resp.json()
  return json.data
}

export async function generateCheatSheet(roomId: number): Promise<CheatSheet> {
  const resp = await fetch(`${API_BASE}/rooms/${roomId}/cheatsheet`, {
    method: 'POST',
  })
  if (!resp.ok) {
    const json = await resp.json().catch(() => null)
    throw new Error(json?.message || `生成失败: ${resp.status}`)
  }
  const json: ApiResponse<CheatSheet> = await resp.json()
  return json.data
}

// ---------------------------------------------------------------------------
// Profile Card
// ---------------------------------------------------------------------------

export interface ProfileTag {
  text: string
  type: 'strength' | 'weakness' | 'trait'
}

export interface ProfileCard {
  style_label: string
  tags: ProfileTag[]
  summary: string
  scores: Record<string, number>
}

export async function generateProfileCard(): Promise<ProfileCard> {
  const resp = await fetch(`${API_BASE}/growth/card`, { method: 'POST' })
  if (!resp.ok) {
    const json = await resp.json().catch(() => null)
    throw new Error(json?.message || `生成失败: ${resp.status}`)
  }
  const json: ApiResponse<ProfileCard> = await resp.json()
  return json.data
}

// ---------------------------------------------------------------------------
// ---------------------------------------------------------------------------
// Speaker Detection
// ---------------------------------------------------------------------------

export interface DetectedSpeaker {
  name: string
  role: string
  speaking_turns: number
  dominance_level: 'low' | 'medium' | 'high'
  sample_quote: string
}

export async function detectSpeakers(
  materials: string[],
): Promise<DetectedSpeaker[]> {
  const resp = await fetch(`${API_BASE}/persona/detect-speakers`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ materials }),
  })
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ message: resp.statusText }))
    throw new Error(err.detail?.message || err.message || `HTTP ${resp.status}`)
  }
  const json = await resp.json()
  return json.data
}

// ---------------------------------------------------------------------------
// Story 2.5 / 2.6 — Persona Build SSE
// ---------------------------------------------------------------------------

export type BuildEventType =
  | 'workspace_ready'
  | 'agent_tool_use'
  | 'agent_message'
  | 'parse_done'
  | 'adversarialize_start'
  | 'adversarialize_done'
  | 'persist_done'
  | 'heartbeat'
  | 'error'
  | 'enhancement_start'
  | 'enhancement_merge'

export interface BuildEvent {
  seq: number
  type: BuildEventType
  ts: number
  data: Record<string, unknown>
}

export interface PersonaBuildRequest {
  materials: string[]
  target_persona_id?: string
  name?: string
  role?: string
}

// ---------------------------------------------------------------------------
// Defense Prep
// ---------------------------------------------------------------------------

export interface DefenseSession {
  id: number
  persona_id: string
  scenario_type: string
  document_title: string
  status: 'preparing' | 'in_progress' | 'completed'
  room_id: number | null
  created_at: string | null
  question_strategy?: {
    questions: { question: string; dimension: string; difficulty: string }[]
  }
}

export interface DefenseReport {
  overall_score: number
  dimension_scores: Record<string, number>
  question_reviews: {
    question: string
    user_answer_summary: string
    score: number
    feedback: string
    improvement: string
  }[]
  summary: string
  top_improvements: string[]
}

export async function createDefenseSession(file: File, personaId: string, scenarioType: string): Promise<DefenseSession> {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('persona_id', personaId)
  formData.append('scenario_type', scenarioType)
  const resp = await fetch(`${API_BASE}/defense-prep/sessions`, { method: 'POST', body: formData })
  if (!resp.ok) {
    const json = await resp.json().catch(() => null)
    throw new Error(json?.message || `创建失败: ${resp.status}`)
  }
  const json: ApiResponse<DefenseSession> = await resp.json()
  return json.data
}

export async function getDefenseSession(sessionId: number): Promise<DefenseSession> {
  const resp = await fetch(`${API_BASE}/defense-prep/sessions/${sessionId}`)
  if (!resp.ok) throw new Error(`获取会话失败: ${resp.status}`)
  const json: ApiResponse<DefenseSession> = await resp.json()
  return json.data
}

export async function startDefenseSession(sessionId: number): Promise<DefenseSession> {
  const resp = await fetch(`${API_BASE}/defense-prep/sessions/${sessionId}/start`, { method: 'POST' })
  if (!resp.ok) {
    const json = await resp.json().catch(() => null)
    throw new Error(json?.message || `启动失败: ${resp.status}`)
  }
  const json: ApiResponse<DefenseSession> = await resp.json()
  return json.data
}

export async function getDefenseReport(sessionId: number): Promise<DefenseReport> {
  const resp = await fetch(`${API_BASE}/defense-prep/sessions/${sessionId}/report`)
  if (!resp.ok) {
    const json = await resp.json().catch(() => null)
    throw new Error(json?.message || `报告生成失败: ${resp.status}`)
  }
  const json: ApiResponse<DefenseReport> = await resp.json()
  return json.data
}
