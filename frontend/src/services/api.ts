const API_BASE = '/api/v1/stakeholder'

export interface PersonaSummary {
  id: string
  name: string
  role: string
  avatar_color: string | null
  parse_status: string
}

export interface PersonaDetail extends PersonaSummary {
  profile_summary: string
  content: string
}

export interface ChatRoom {
  id: number
  name: string
  type: 'private' | 'group'
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
  data: { name?: string; role?: string; avatar_color?: string; content?: string },
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

export async function listAnalysisReports(roomId: number): Promise<{ id: number }[]> {
  const resp = await fetch(`${API_BASE}/rooms/${roomId}/analysis`)
  if (!resp.ok) throw new Error(`Failed to list analysis reports: ${resp.status}`)
  const json: ApiResponse<{ id: number }[]> = await resp.json()
  return json.data
}

export async function createAnalysisReport(roomId: number): Promise<{ id: number }> {
  const resp = await fetch(`${API_BASE}/rooms/${roomId}/analysis`, { method: 'POST' })
  if (!resp.ok) throw new Error(`Failed to create analysis report: ${resp.status}`)
  const json: ApiResponse<{ id: number }> = await resp.json()
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
