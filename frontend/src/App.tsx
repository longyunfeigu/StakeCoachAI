import React, { useEffect, useRef, useState } from 'react'
import Markdown from 'react-markdown'
import './App.css'
import RoomList from './components/RoomList'
import CreateRoomDialog from './components/CreateRoomDialog'
import PersonaEditorDialog from './components/PersonaEditorDialog'
import ScenarioDialog from './components/ScenarioDialog'
import EmotionCurve from './components/EmotionCurve'
import {
  fetchPersonas,
  fetchRoomDetail,
  sendMessage,
  exportRoom,
  exportRoomHtml,
  listAnalysisReports,
  createAnalysisReport,
  startCoachingStream,
  sendCoachingMessageStream,
  type ChatRoom,
  type ChatRoomDetail,
  type CoachingMessageItem,
  type DispatchPhase,
  type Message,
  type PersonaSummary,
  type RoundEndData,
} from './services/api'

const API_BASE = '/api/v1/stakeholder'

function formatTime(ts: string | null): string {
  if (!ts) return ''
  const d = new Date(ts)
  if (isNaN(d.getTime())) return ''
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

/** Highlight @mentions inside a plain text string */
function highlightMentions(text: string): React.ReactNode {
  const parts = text.split(/(@[\w\u4e00-\u9fff]+)/g)
  if (parts.length === 1) return text
  return parts.map((part, i) =>
    part.startsWith('@') ? (
      <span key={i} className="mention-highlight">{part}</span>
    ) : (
      part
    ),
  )
}

/** Recursively walk React children, applying @mention highlights to string nodes */
function withMentions(children: React.ReactNode): React.ReactNode {
  if (typeof children === 'string') return highlightMentions(children)
  if (Array.isArray(children)) {
    return children.map((child, i) =>
      typeof child === 'string'
        ? <React.Fragment key={i}>{highlightMentions(child)}</React.Fragment>
        : child,
    )
  }
  return children
}

/** Render message content as Markdown with @mention highlights */
function renderContent(text: string) {
  return (
    <Markdown
      components={{
        p: ({ children }) => <p>{withMentions(children)}</p>,
        li: ({ children }) => <li>{withMentions(children)}</li>,
      }}
    >
      {text}
    </Markdown>
  )
}

function App() {
  const [selectedRoom, setSelectedRoom] = useState<ChatRoomDetail | null>(null)
  const [selectedRoomId, setSelectedRoomId] = useState<number | null>(null)
  const [showCreateDialog, setShowCreateDialog] = useState(false)
  const [showScenarioDialog, setShowScenarioDialog] = useState(false)
  const [showEmotionCurve, setShowEmotionCurve] = useState(false)
  const [showExportMenu, setShowExportMenu] = useState(false)
  const [personaEditorState, setPersonaEditorState] = useState<{
    open: boolean
    persona: PersonaSummary | null
  }>({ open: false, persona: null })
  const [refreshKey, setRefreshKey] = useState(0)
  const [inputValue, setInputValue] = useState('')
  const [sending, setSending] = useState(false)
  const [typingPersona, setTypingPersona] = useState<string | null>(null)
  const [personaMap, setPersonaMap] = useState<Record<string, PersonaSummary>>({})
  // Streaming content per persona -- isolated from messages array to avoid dedup issues
  const [streamingContent, setStreamingContent] = useState<Record<string, string>>({})
  // Dispatcher transparency: shows why each persona was chosen
  const [dispatchSummary, setDispatchSummary] = useState<DispatchPhase[] | null>(null)
  const [dispatchExpanded, setDispatchExpanded] = useState(false)
  // Coaching panel state
  const [coachingOpen, setCoachingOpen] = useState(false)
  const [coachingSessionId, setCoachingSessionId] = useState<number | null>(null)
  const [coachingMessages, setCoachingMessages] = useState<CoachingMessageItem[]>([])
  const [coachingStreaming, setCoachingStreaming] = useState('')
  const [coachingSending, setCoachingSending] = useState(false)
  const [coachingInput, setCoachingInput] = useState('')
  const coachingListRef = useRef<HTMLDivElement>(null)
  // @mention autocomplete state
  const [mentionQuery, setMentionQuery] = useState<string | null>(null)
  const [mentionResults, setMentionResults] = useState<PersonaSummary[]>([])
  const messageListRef = useRef<HTMLDivElement>(null)
  const eventSourceRef = useRef<EventSource | null>(null)

  // Load persona map
  const loadPersonas = () => {
    fetchPersonas()
      .then((personas) => {
        const map: Record<string, PersonaSummary> = {}
        for (const p of personas) {
          map[p.id] = p
        }
        setPersonaMap(map)
      })
      .catch(() => {})
  }

  useEffect(() => {
    loadPersonas()
  }, [])

  const scrollToBottom = () => {
    if (messageListRef.current) {
      messageListRef.current.scrollTop = messageListRef.current.scrollHeight
    }
  }

  // SSE connection management
  useEffect(() => {
    if (!selectedRoomId) return

    // Close previous connection
    if (eventSourceRef.current) {
      eventSourceRef.current.close()
      eventSourceRef.current = null
    }

    const es = new EventSource(`${API_BASE}/rooms/${selectedRoomId}/stream`)
    eventSourceRef.current = es

    es.addEventListener('message', (e) => {
      const msg: Message = JSON.parse(e.data)
      // Clear streaming content for this persona -- the final message replaces it
      if (msg.sender_type === 'persona') {
        setStreamingContent((prev) => {
          const next = { ...prev }
          delete next[msg.sender_id]
          return next
        })
      }
      setSelectedRoom((prev) => {
        if (!prev || prev.room.id !== msg.room_id) return prev
        // Avoid duplicates
        const exists = prev.messages.some((m) => m.id === msg.id)
        if (exists) return prev
        return { ...prev, messages: [...prev.messages, msg] }
      })
      setTimeout(scrollToBottom, 50)
    })

    es.addEventListener('streaming_delta', (e) => {
      const data: { persona_id: string; delta: string } = JSON.parse(e.data)
      setStreamingContent((prev) => ({
        ...prev,
        [data.persona_id]: (prev[data.persona_id] || '') + data.delta,
      }))
      setTimeout(scrollToBottom, 30)
    })

    es.addEventListener('typing', (e) => {
      const data = JSON.parse(e.data)
      if (data.status === 'start') {
        setTypingPersona(data.persona_id)
      } else {
        setTypingPersona(null)
        // Fallback cleanup of streaming content
        setStreamingContent((prev) => {
          const next = { ...prev }
          delete next[data.persona_id]
          return next
        })
      }
    })

    es.addEventListener('round_end', (e) => {
      setTypingPersona(null)
      setStreamingContent({})
      try {
        const data: RoundEndData = JSON.parse(e.data)
        if (data.dispatch_log && data.dispatch_log.length > 0) {
          setDispatchSummary(data.dispatch_log)
          setDispatchExpanded(false)
        }
      } catch {
        // Backward compat: old backend may send empty payload
      }
    })

    es.onerror = () => {
      setTypingPersona(null)
    }

    return () => {
      es.close()
      eventSourceRef.current = null
      setTypingPersona(null)
      setStreamingContent({})
    }
  }, [selectedRoomId])

  const handleSelectRoom = async (room: ChatRoom) => {
    setSelectedRoomId(room.id)
    setTypingPersona(null)
    setStreamingContent({})
    try {
      const detail = await fetchRoomDetail(room.id)
      setSelectedRoom(detail)
      setTimeout(scrollToBottom, 50)
    } catch {
      setSelectedRoom(null)
    }
  }

  const handleRoomCreated = async (roomId: number) => {
    setRefreshKey((k) => k + 1)
    setSelectedRoomId(roomId)
    try {
      const detail = await fetchRoomDetail(roomId)
      setSelectedRoom(detail)
    } catch {
      setSelectedRoom(null)
    }
  }

  const handleSend = async () => {
    const content = inputValue.trim()
    if (!content || !selectedRoomId || sending) return

    setSending(true)
    setInputValue('')
    setMentionQuery(null)
    setMentionResults([])
    setDispatchSummary(null)

    try {
      await sendMessage(selectedRoomId, content)
      // SSE will push the messages -- just refresh room list for ordering
      setRefreshKey((k) => k + 1)
      setTimeout(scrollToBottom, 100)
    } catch (e: any) {
      console.error('Send failed:', e)
      // Fallback: refresh room detail
      if (selectedRoomId) {
        const detail = await fetchRoomDetail(selectedRoomId)
        setSelectedRoom(detail)
        setTimeout(scrollToBottom, 50)
      }
    } finally {
      setSending(false)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      // If mention dropdown is visible, don't send -- let user pick
      if (mentionQuery !== null && mentionResults.length > 0) {
        e.preventDefault()
        insertMention(mentionResults[0])
        return
      }
      e.preventDefault()
      handleSend()
    }
  }

  // @mention detection
  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value
    setInputValue(val)

    const atMatch = val.match(/@([\w\u4e00-\u9fff]*)$/)
    if (atMatch && selectedRoom?.room.type === 'group') {
      const query = atMatch[1].toLowerCase()
      const matches = Object.values(personaMap).filter(
        (p) =>
          p.name.toLowerCase().includes(query) ||
          p.id.toLowerCase().includes(query),
      )
      setMentionQuery(atMatch[1])
      setMentionResults(matches)
    } else {
      setMentionQuery(null)
      setMentionResults([])
    }
  }

  const insertMention = (persona: PersonaSummary) => {
    setInputValue((prev) =>
      prev.replace(/@[\w\u4e00-\u9fff]*$/, `@${persona.name} `),
    )
    setMentionQuery(null)
    setMentionResults([])
  }

  // Collect streaming entries for rendering
  // ---------------------------------------------------------------------------
  // Coaching helpers
  // ---------------------------------------------------------------------------

  const scrollCoachingToBottom = () => {
    if (coachingListRef.current) {
      coachingListRef.current.scrollTop = coachingListRef.current.scrollHeight
    }
  }

  async function processCoachingSSE(resp: globalThis.Response) {
    const reader = resp.body?.getReader()
    if (!reader) return
    const decoder = new TextDecoder()
    let buffer = ''
    let streamedText = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })

      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        if (line.startsWith('event: ')) {
          continue
        }
        if (line.startsWith('data: ')) {
          const raw = line.slice(6)
          try {
            const data = JSON.parse(raw)
            if (data.session_id !== undefined) {
              // session_created
              setCoachingSessionId(data.session_id)
            } else if (data.content !== undefined && data.message_id === undefined) {
              // message_delta
              streamedText += data.content
              setCoachingStreaming(streamedText)
              setTimeout(scrollCoachingToBottom, 30)
            } else if (data.message_id !== undefined) {
              // message_complete
              const msg: CoachingMessageItem = {
                id: data.message_id,
                session_id: coachingSessionId || 0,
                role: data.role,
                content: data.content,
                created_at: null,
              }
              setCoachingMessages((prev) => [...prev, msg])
              setCoachingStreaming('')
              streamedText = ''
              setTimeout(scrollCoachingToBottom, 50)
            }
          } catch {
            // ignore parse errors
          }
        }
      }
    }
  }

  const handleStartCoaching = async () => {
    if (!selectedRoomId) return
    setCoachingOpen(true)
    setCoachingMessages([])
    setCoachingStreaming('')
    setCoachingSessionId(null)
    setCoachingSending(true)

    try {
      // Get latest analysis report, or create one if none exists
      let reports = await listAnalysisReports(selectedRoomId)
      let reportId: number
      if (reports.length > 0) {
        reportId = reports[reports.length - 1].id
      } else {
        const created = await createAnalysisReport(selectedRoomId)
        reportId = created.id
      }

      const resp = await startCoachingStream(selectedRoomId, reportId)
      if (resp instanceof Response) {
        await processCoachingSSE(resp)
      }
    } catch (e) {
      console.error('Start coaching failed:', e)
    } finally {
      setCoachingSending(false)
    }
  }

  const handleSendCoaching = async () => {
    const content = coachingInput.trim()
    if (!content || !selectedRoomId || !coachingSessionId || coachingSending) return
    setCoachingInput('')
    setCoachingSending(true)

    // Add user message optimistically
    const tempMsg: CoachingMessageItem = {
      id: Date.now(),
      session_id: coachingSessionId,
      role: 'user',
      content,
      created_at: null,
    }
    setCoachingMessages((prev) => [...prev, tempMsg])
    setTimeout(scrollCoachingToBottom, 50)

    try {
      const resp = await sendCoachingMessageStream(selectedRoomId, coachingSessionId, content)
      if (resp instanceof Response) {
        await processCoachingSSE(resp)
      }
    } catch (e) {
      console.error('Send coaching message failed:', e)
    } finally {
      setCoachingSending(false)
    }
  }


  const streamingEntries = Object.entries(streamingContent)

  return (
    <div className="app-layout">
      <aside className="sidebar">
        <h2>Stakeholder Chat</h2>

        {/* Persona panel */}
        <div className="persona-panel">
          <div className="persona-panel-header">
            <span className="persona-panel-title">角色</span>
            <button
              className="sidebar-icon-btn"
              onClick={() => setShowScenarioDialog(true)}
              title="场景管理"
            >
              场景
            </button>
          </div>
          {Object.values(personaMap).map((p) => (
            <div
              key={p.id}
              className="persona-item"
              onClick={() =>
                setPersonaEditorState({ open: true, persona: p })
              }
            >
              <span
                className="persona-dot"
                style={{ background: p.avatar_color || '#999' }}
              />
              <span>{p.name}</span>
            </div>
          ))}
          <button
            className="add-persona-btn"
            onClick={() =>
              setPersonaEditorState({ open: true, persona: null })
            }
          >
            + 新建角色
          </button>
        </div>

        <RoomList
          selectedRoomId={selectedRoomId}
          onSelectRoom={handleSelectRoom}
          onCreateRoom={() => setShowCreateDialog(true)}
          onRoomDeleted={(id) => {
            if (selectedRoomId === id) {
              setSelectedRoomId(null)
              setSelectedRoom(null)
            }
          }}
          refreshKey={refreshKey}
        />
      </aside>
      <main className="main-content">
        {selectedRoom ? (
          <div className="chat-view">
            <div className="chat-header">
              <h3>{selectedRoom.room.name}</h3>
              <span className={`room-type-badge ${selectedRoom.room.type}`}>
                {selectedRoom.room.type === 'private' ? '私聊' : '群聊'}
              </span>
              <button
                className="export-btn"
                onClick={() => setShowEmotionCurve(true)}
                title="查看角色情绪曲线"
              >
                情绪
              </button>
              <button
                className="coaching-btn"
                onClick={() => handleStartCoaching()}
                title="基于分析报告的交互式复盘"
                disabled={coachingSending}
              >
                复盘
              </button>
              <div className="export-dropdown-wrapper">
                <button
                  className="export-btn"
                  onClick={() => setShowExportMenu((v) => !v)}
                >
                  导出 ▾
                </button>
                {showExportMenu && (
                  <div className="export-menu">
                    <div
                      className="export-menu-item"
                      onClick={() => {
                        setShowExportMenu(false)
                        exportRoomHtml(selectedRoom.room.id).catch(console.error)
                      }}
                    >
                      HTML 格式
                      <span className="export-menu-desc">保留聊天样式</span>
                    </div>
                    <div
                      className="export-menu-item"
                      onClick={() => {
                        setShowExportMenu(false)
                        exportRoom(selectedRoom.room.id).catch(console.error)
                      }}
                    >
                      Markdown 格式
                      <span className="export-menu-desc">纯文本，便于编辑</span>
                    </div>
                  </div>
                )}
              </div>
            </div>
            <div className="message-list" ref={messageListRef} onClick={() => showExportMenu && setShowExportMenu(false)}>
              {selectedRoom.messages.length === 0 && streamingEntries.length === 0 ? (
                <div className="empty-messages">暂无消息，发送第一条消息开始对话</div>
              ) : (
                <>
                  {selectedRoom.messages.map((msg) => {
                    const persona = msg.sender_type === 'persona' ? personaMap[msg.sender_id] : null
                    const borderColor = persona?.avatar_color || undefined
                    return (
                      <div key={msg.id} className={`message ${msg.sender_type}`} data-sender={msg.sender_type}>
                        {msg.sender_type === 'persona' && (
                          <div className="sender-name" style={borderColor ? { color: borderColor } : undefined}>
                            {persona?.name || msg.sender_id}
                            {msg.emotion_label && (
                              <span className={`emotion-tag ${(msg.emotion_score ?? 0) > 0 ? 'positive' : (msg.emotion_score ?? 0) < 0 ? 'negative' : 'neutral'}`}>
                                {msg.emotion_label}
                              </span>
                            )}
                          </div>
                        )}
                        <div
                          className="message-bubble"
                          style={borderColor ? { borderLeft: `3px solid ${borderColor}` } : undefined}
                        >
                          {renderContent(msg.content)}
                        </div>
                        <div className="message-time">{formatTime(msg.timestamp)}</div>
                      </div>
                    )
                  })}
                  {/* Streaming messages -- in-progress persona replies */}
                  {streamingEntries.map(([personaId, text]) => {
                    const persona = personaMap[personaId]
                    const borderColor = persona?.avatar_color || undefined
                    return (
                      <div key={`streaming-${personaId}`} className="message persona streaming" data-sender="persona">
                        <div className="sender-name" style={borderColor ? { color: borderColor } : undefined}>
                          {persona?.name || personaId}
                        </div>
                        <div
                          className="message-bubble"
                          style={borderColor ? { borderLeft: `3px solid ${borderColor}` } : undefined}
                        >
                          {renderContent(text)}
                          <span className="streaming-cursor" />
                        </div>
                      </div>
                    )
                  })}
                </>
              )}
              {/* Dispatcher transparency: collapsible dispatch summary */}
              {dispatchSummary && dispatchSummary.length > 0 && (
                <div className="dispatch-summary" onClick={() => setDispatchExpanded((v) => !v)}>
                  <div className="dispatch-summary-header">
                    <span className="dispatch-summary-icon">&#128203;</span>
                    <span>
                      本轮{' '}
                      {dispatchSummary.reduce((n, p) => n + p.responders.length, 0)}{' '}
                      位角色参与讨论
                    </span>
                    <span className={`dispatch-expand-arrow ${dispatchExpanded ? 'expanded' : ''}`}>&#9662;</span>
                  </div>
                  {dispatchExpanded && (
                    <div className="dispatch-summary-body">
                      {dispatchSummary.map((phase, i) => (
                        <div key={i} className="dispatch-phase">
                          <div className="dispatch-phase-label">
                            {phase.phase === 'initial'
                              ? '初始响应'
                              : `跟进讨论${phase.trigger_persona_id ? `（由 ${personaMap[phase.trigger_persona_id]?.name || phase.trigger_persona_id} 触发）` : ''}`}
                          </div>
                          <ul className="dispatch-responders">
                            {phase.responders.map((r) => (
                              <li key={r.persona_id}>
                                <strong style={{ color: personaMap[r.persona_id]?.avatar_color || undefined }}>
                                  {personaMap[r.persona_id]?.name || r.persona_id}
                                </strong>
                                {' — '}
                                {r.reason || '参与讨论'}
                              </li>
                            ))}
                          </ul>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
              {typingPersona && streamingEntries.length === 0 && (
                <div className="typing-indicator">
                  {personaMap[typingPersona]?.name || typingPersona} 正在回复...
                </div>
              )}
            </div>
            <div className="message-input-bar">
              {mentionQuery !== null && mentionResults.length > 0 && (
                <div className="mention-dropdown">
                  {mentionResults.map((p) => (
                    <div
                      key={p.id}
                      className="mention-item"
                      onClick={() => insertMention(p)}
                    >
                      <span
                        className="persona-dot"
                        style={{ background: p.avatar_color || '#999' }}
                      />
                      {p.name}{' '}
                      <span className="mention-role">{p.role}</span>
                    </div>
                  ))}
                </div>
              )}
              <input
                type="text"
                value={inputValue}
                onChange={handleInputChange}
                onKeyDown={handleKeyDown}
                placeholder={
                  selectedRoom.room.type === 'group'
                    ? '输入消息... 使用 @ 提及角色'
                    : '输入消息...'
                }
                disabled={sending}
              />
              <button onClick={handleSend} disabled={!inputValue.trim() || sending}>
                {sending ? '...' : '发送'}
              </button>
            </div>
          </div>
        ) : (
          <p className="main-placeholder">选择或创建一个聊天室开始对话</p>
        )}
      </main>

      {/* Coaching side panel */}
      {coachingOpen && (
        <aside className="coaching-panel">
          <div className="coaching-header">
            <h3>AI Coach 复盘</h3>
            <button className="coaching-close" onClick={() => setCoachingOpen(false)}>×</button>
          </div>
          <div className="coaching-messages" ref={coachingListRef}>
            {coachingMessages.map((msg) => (
              <div key={msg.id} className={`coaching-msg ${msg.role}`}>
                <div className="coaching-msg-role">{msg.role === 'coach' ? 'Coach' : '你'}</div>
                <div className="coaching-msg-bubble">
                  <Markdown>{msg.content}</Markdown>
                </div>
              </div>
            ))}
            {coachingStreaming && (
              <div className="coaching-msg coach streaming">
                <div className="coaching-msg-role">Coach</div>
                <div className="coaching-msg-bubble">
                  <Markdown>{coachingStreaming}</Markdown>
                  <span className="streaming-cursor" />
                </div>
              </div>
            )}
            {coachingSending && !coachingStreaming && coachingMessages.length === 0 && (
              <div className="coaching-loading">Coach 正在思考...</div>
            )}
          </div>
          <div className="coaching-input-bar">
            <input
              type="text"
              value={coachingInput}
              onChange={(e) => setCoachingInput(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSendCoaching() } }}
              placeholder="回复 Coach..."
              disabled={coachingSending || !coachingSessionId}
            />
            <button onClick={handleSendCoaching} disabled={!coachingInput.trim() || coachingSending || !coachingSessionId}>
              发送
            </button>
          </div>
        </aside>
      )}

      <CreateRoomDialog
        open={showCreateDialog}
        onClose={() => setShowCreateDialog(false)}
        onCreated={handleRoomCreated}
      />

      <PersonaEditorDialog
        open={personaEditorState.open}
        onClose={() => setPersonaEditorState({ open: false, persona: null })}
        onSaved={loadPersonas}
        editingPersona={personaEditorState.persona}
      />

      <ScenarioDialog
        open={showScenarioDialog}
        onClose={() => setShowScenarioDialog(false)}
      />

      <EmotionCurve
        open={showEmotionCurve}
        onClose={() => setShowEmotionCurve(false)}
        messages={selectedRoom?.messages || []}
        personaMap={personaMap}
      />
    </div>
  )
}

export default App
