import React, { useEffect, useRef, useState } from 'react'
import Markdown from 'react-markdown'
import { MessageCircle, Layers, Plus, BarChart3, BarChart2, GraduationCap, Download, FileText, FileDown, Send, ClipboardList, X, Building2, TrendingUp, Activity } from 'lucide-react'
import './App.css'
import Avatar from './components/Avatar'
import RoomList from './components/RoomList'
import CreateRoomDialog from './components/CreateRoomDialog'
import PersonaEditorDialog from './components/PersonaEditorDialog'
import ScenarioDialog from './components/ScenarioDialog'
import OrganizationDialog from './components/OrganizationDialog'
import EmotionCurve from './components/EmotionCurve'
import EmotionSidebar from './components/EmotionSidebar'
import GrowthDashboard from './components/GrowthDashboard'
import {
  fetchPersonas,
  fetchOrganizations,
  fetchRoomDetail,
  sendMessage,
  exportRoom,
  exportRoomHtml,
  listAnalysisReports,
  createAnalysisReport,
  fetchAnalysisReport,
  startCoachingStream,
  sendCoachingMessageStream,
  type ChatRoom,
  type ChatRoomDetail,
  type CoachingMessageItem,
  type DispatchPhase,
  type Message,
  type Organization,
  type PersonaSummary,
  type RoundEndData,
  type AnalysisReport,
  type AnalysisReportSummary,
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
  const [showOrgDialog, setShowOrgDialog] = useState(false)
  const [showGrowth, setShowGrowth] = useState(false)
  const [currentOrg, setCurrentOrg] = useState<Organization | null>(null)
  const [showEmotionSidebar, setShowEmotionSidebar] = useState(false)
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
  // Analysis panel state
  const [analysisResult, setAnalysisResult] = useState<AnalysisReport | null>(null)
  const [analyzingRoom, setAnalyzingRoom] = useState(false)
  const [analysisReportList, setAnalysisReportList] = useState<AnalysisReportSummary[]>([])
  const [highlightedMessageId, setHighlightedMessageId] = useState<number | null>(null)
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

  const loadOrg = () => {
    fetchOrganizations()
      .then((orgs) => {
        if (orgs.length > 0) setCurrentOrg(orgs[0])
        else setCurrentOrg(null)
      })
      .catch(() => {})
  }

  useEffect(() => {
    loadPersonas()
    loadOrg()
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
    setShowGrowth(false)
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
      const roomPids = new Set(selectedRoom.room.persona_ids)
      const matches = Object.values(personaMap).filter(
        (p) =>
          roomPids.has(p.id) &&
          (p.name.toLowerCase().includes(query) ||
          p.id.toLowerCase().includes(query)),
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

  const handleAnalyze = async () => {
    if (!selectedRoomId || analyzingRoom) return
    setAnalyzingRoom(true)
    setAnalysisResult(null)
    try {
      // Load existing reports list
      const reports = await listAnalysisReports(selectedRoomId)
      setAnalysisReportList(reports)

      if (reports.length > 0) {
        // Show latest existing report (API returns newest first)
        const latest = reports[0]
        const full = await fetchAnalysisReport(selectedRoomId, latest.id)
        setAnalysisResult(full)
      } else {
        // No reports yet, generate a new one
        const report = await createAnalysisReport(selectedRoomId)
        setAnalysisResult(report)
        setAnalysisReportList([{ id: report.id, room_id: report.room_id, summary: report.summary, created_at: report.created_at }])
      }
    } catch (e: any) {
      const msg = e?.message || '分析失败'
      if (msg.includes('No messages') || msg.includes('NoMessages')) {
        alert('暂无消息可分析，请先发送消息后再试')
      } else {
        alert(msg)
      }
    } finally {
      setAnalyzingRoom(false)
    }
  }

  const handleGenerateNewReport = async () => {
    if (!selectedRoomId || analyzingRoom) return
    setAnalyzingRoom(true)
    try {
      const report = await createAnalysisReport(selectedRoomId)
      setAnalysisResult(report)
      // Refresh list
      const reports = await listAnalysisReports(selectedRoomId)
      setAnalysisReportList(reports)
    } catch (e: any) {
      alert(e?.message || '生成失败')
    } finally {
      setAnalyzingRoom(false)
    }
  }

  const handleSelectReport = async (reportId: number) => {
    if (!selectedRoomId) return
    try {
      const full = await fetchAnalysisReport(selectedRoomId, reportId)
      setAnalysisResult(full)
    } catch {
      alert('加载报告失败')
    }
  }

  const handleScrollToMessage = (messageIndices: number[] | undefined, messageIdMap: Record<string, number> | undefined) => {
    if (!messageIndices?.length || !messageIdMap) return
    // Find the first valid message ID
    for (const idx of messageIndices) {
      const msgId = messageIdMap[String(idx)]
      if (msgId == null) continue
      // Close dialog
      setAnalysisResult(null)
      // Scroll to message after dialog closes
      setTimeout(() => {
        const el = document.getElementById(`msg-${msgId}`)
        if (el) {
          el.scrollIntoView({ behavior: 'smooth', block: 'center' })
          setHighlightedMessageId(msgId)
          setTimeout(() => setHighlightedMessageId(null), 2500)
        }
      }, 100)
      return
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
        reportId = reports[0].id
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
        <div className="sidebar-brand">
          <div className="sidebar-brand-icon"><MessageCircle size={20} /></div>
          <div>
            <div className="sidebar-brand-name">StakeCoach AI</div>
            <div className="sidebar-brand-sub">利益相关者沟通教练</div>
          </div>
        </div>

        {/* Organization section */}
        <div className="org-section">
          <div className="org-section-header">
            <span className="sidebar-section-title">组织</span>
          </div>
          <div className="org-badge" onClick={() => setShowOrgDialog(true)}>
            <Building2 size={14} />
            {currentOrg ? (
              <span className="org-badge-name">{currentOrg.name}</span>
            ) : (
              <span style={{ color: 'var(--text-muted)' }}>点击创建组织</span>
            )}
          </div>
        </div>

        {/* Persona panel */}
        <div className="persona-panel">
          <div className="sidebar-section-header">
            <span className="sidebar-section-title">角色</span>
            <div className="sidebar-section-actions">
              <button
                className="sidebar-icon-btn"
                onClick={() => setShowScenarioDialog(true)}
                title="场景管理"
              >
                <Layers size={14} />
              </button>
              <button
                className="sidebar-icon-btn"
                onClick={() => setPersonaEditorState({ open: true, persona: null })}
                title="新建角色"
              >
                <Plus size={14} />
              </button>
            </div>
          </div>
          {Object.values(personaMap).map((p) => (
            <div
              key={p.id}
              className="persona-item"
              onClick={() =>
                setPersonaEditorState({ open: true, persona: p })
              }
            >
              <Avatar name={p.name} color={p.avatar_color || '#2D9C6F'} size={28} />
              <div className="persona-item-info">
                <span className="persona-item-name">{p.name}</span>
                <span className="persona-item-role">{p.role}</span>
              </div>
            </div>
          ))}
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

        {/* Growth tab button */}
        <button
          className={`growth-btn ${showGrowth ? 'active' : ''}`}
          onClick={() => {
            setShowGrowth(true)
            setSelectedRoomId(null)
            setSelectedRoom(null)
          }}
        >
          <TrendingUp size={16} />
          <span>成长轨迹</span>
        </button>
      </aside>
      <main className="main-content">
        {showGrowth ? (
          <GrowthDashboard onCreateRoom={() => setShowCreateDialog(true)} />
        ) : selectedRoom ? (
          <div className="chat-with-emotion">
          <div className="chat-view">
            <div className="chat-header">
              <div className="chat-header-left">
                <h3>{selectedRoom.room.name}</h3>
                <span className={`room-type-badge ${selectedRoom.room.type}`}>
                  {selectedRoom.room.type === 'private' ? '私聊' : '群聊'}
                </span>
              </div>
              <div className="chat-header-actions">
                <button
                  className={`header-action-btn ${showEmotionSidebar ? 'active' : ''}`}
                  onClick={() => setShowEmotionSidebar((v) => !v)}
                  title="实时情绪面板"
                >
                  <Activity size={16} />
                </button>
                <button
                  className="header-action-btn"
                  onClick={() => setShowEmotionCurve(true)}
                  title="情绪详细分析"
                >
                  <BarChart3 size={16} />
                </button>
                <button
                  className="header-action-btn"
                  onClick={handleAnalyze}
                  title="分析"
                  disabled={analyzingRoom}
                >
                  <BarChart2 size={16} />
                </button>
                <button
                  className="header-action-btn coaching"
                  onClick={() => handleStartCoaching()}
                  title="AI 复盘"
                  disabled={coachingSending}
                >
                  <GraduationCap size={16} />
                </button>
                <div className="export-dropdown-wrapper">
                  <button
                    className="header-action-btn"
                    onClick={() => setShowExportMenu((v) => !v)}
                    title="导出"
                  >
                    <Download size={16} />
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
                        <FileText size={15} />
                        <div>
                          <div>HTML 格式</div>
                          <span className="export-menu-desc">保留聊天样式</span>
                        </div>
                      </div>
                      <div
                        className="export-menu-item"
                        onClick={() => {
                          setShowExportMenu(false)
                          exportRoom(selectedRoom.room.id).catch(console.error)
                        }}
                      >
                        <FileDown size={15} />
                        <div>
                          <div>Markdown 格式</div>
                          <span className="export-menu-desc">纯文本，便于编辑</span>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </div>
            <div className="message-list" ref={messageListRef} onClick={() => showExportMenu && setShowExportMenu(false)}>
              {selectedRoom.messages.length === 0 && streamingEntries.length === 0 ? (
                <div className="empty-messages">
                  <MessageCircle size={36} strokeWidth={1.2} />
                  <p>发送第一条消息，开始模拟对话</p>
                </div>
              ) : (
                <>
                  {selectedRoom.messages.map((msg) => {
                    const persona = msg.sender_type === 'persona' ? personaMap[msg.sender_id] : null
                    const borderColor = persona?.avatar_color || undefined
                    return (
                      <div key={msg.id} id={`msg-${msg.id}`} className={`message ${msg.sender_type}${highlightedMessageId === msg.id ? ' highlighted' : ''}`} data-sender={msg.sender_type}>
                        {msg.sender_type === 'persona' && (
                          <div className="message-row">
                            <Avatar name={persona?.name || msg.sender_id} color={borderColor || '#2D9C6F'} size={28} />
                            <div className="message-content">
                              <div className="sender-name" style={borderColor ? { color: borderColor } : undefined}>
                                {persona?.name || msg.sender_id}
                                {msg.emotion_label && (
                                  <span className={`emotion-tag ${(msg.emotion_score ?? 0) > 0 ? 'positive' : (msg.emotion_score ?? 0) < 0 ? 'negative' : 'neutral'}`}>
                                    {msg.emotion_label}
                                  </span>
                                )}
                              </div>
                              <div
                                className="message-bubble"
                                style={borderColor ? { borderLeft: `2px solid ${borderColor}` } : undefined}
                              >
                                {renderContent(msg.content)}
                              </div>
                              <div className="message-time">{formatTime(msg.timestamp)}</div>
                            </div>
                          </div>
                        )}
                        {msg.sender_type === 'user' && (
                          <>
                            <div className="message-bubble">
                              {renderContent(msg.content)}
                            </div>
                            <div className="message-time">{formatTime(msg.timestamp)}</div>
                          </>
                        )}
                        {msg.sender_type === 'system' && (
                          <div className="message-bubble">
                            {renderContent(msg.content)}
                          </div>
                        )}
                      </div>
                    )
                  })}
                  {/* Streaming messages -- in-progress persona replies */}
                  {streamingEntries.map(([personaId, text]) => {
                    const persona = personaMap[personaId]
                    const borderColor = persona?.avatar_color || undefined
                    return (
                      <div key={`streaming-${personaId}`} className="message persona streaming" data-sender="persona">
                        <div className="message-row">
                          <Avatar name={persona?.name || personaId} color={borderColor || '#2D9C6F'} size={28} />
                          <div className="message-content">
                            <div className="sender-name" style={borderColor ? { color: borderColor } : undefined}>
                              {persona?.name || personaId}
                            </div>
                            <div
                              className="message-bubble"
                              style={borderColor ? { borderLeft: `2px solid ${borderColor}` } : undefined}
                            >
                              {renderContent(text)}
                              <span className="streaming-cursor" />
                            </div>
                          </div>
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
                    <ClipboardList size={15} className="dispatch-summary-icon" />
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
                  <div className="typing-dots"><span /><span /><span /></div>
                  {personaMap[typingPersona]?.name || typingPersona} 正在回复
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
                      <Avatar name={p.name} color={p.avatar_color || '#2D9C6F'} size={24} />
                      <span className="mention-name">{p.name}</span>
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
              <button className="send-btn" onClick={handleSend} disabled={!inputValue.trim() || sending}>
                <Send size={18} />
              </button>
            </div>
          </div>
          {showEmotionSidebar && (
            <EmotionSidebar
              messages={selectedRoom?.messages || []}
              personaMap={personaMap}
              onClose={() => setShowEmotionSidebar(false)}
              onExpand={() => setShowEmotionCurve(true)}
            />
          )}
          </div>
        ) : (
          <div className="welcome-page">
            <div className="welcome-icon">
              <MessageCircle size={48} strokeWidth={1.5} />
            </div>
            <h2 className="welcome-title">开始一场对话</h2>
            <p className="welcome-desc">
              创建聊天室，与 AI 角色进行利益相关者沟通模拟，<br />
              提升你的沟通策略与应变能力。
            </p>
            <button className="welcome-cta" onClick={() => setShowCreateDialog(true)}>
              <Plus size={18} />
              新建聊天室
            </button>
          </div>
        )}
      </main>

      {/* Coaching side panel */}
      {coachingOpen && (
        <aside className="coaching-panel">
          <div className="coaching-header">
            <GraduationCap size={18} />
            <h3>AI Coach 复盘</h3>
            <button className="coaching-close" onClick={() => setCoachingOpen(false)}>
              <X size={18} />
            </button>
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
              <div className="coaching-loading">
                <div className="typing-dots"><span /><span /><span /></div>
                Coach 正在思考
              </div>
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
            <button className="send-btn coaching-send" onClick={handleSendCoaching} disabled={!coachingInput.trim() || coachingSending || !coachingSessionId}>
              <Send size={16} />
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
        currentOrg={currentOrg}
      />

      <ScenarioDialog
        open={showScenarioDialog}
        onClose={() => setShowScenarioDialog(false)}
      />

      <OrganizationDialog
        open={showOrgDialog}
        onClose={() => setShowOrgDialog(false)}
        onOrgChanged={() => { loadOrg(); loadPersonas() }}
        personas={Object.values(personaMap)}
      />

      <EmotionCurve
        open={showEmotionCurve}
        onClose={() => setShowEmotionCurve(false)}
        messages={selectedRoom?.messages || []}
        personaMap={personaMap}
      />

      {/* Analysis result dialog */}
      {analysisResult && (
        <div className="dialog-overlay" onClick={() => setAnalysisResult(null)}>
          <div className="dialog analysis-dialog" onClick={(e) => e.stopPropagation()}>
            <div className="analysis-header">
              <h3>对话分析报告</h3>
              <button className="analysis-close" onClick={() => setAnalysisResult(null)}>
                <X size={18} />
              </button>
            </div>

            {/* Historical report selector */}
            {analysisReportList.length > 1 && (
              <div className="analysis-report-selector">
                <select
                  value={analysisResult.id}
                  onChange={(e) => handleSelectReport(Number(e.target.value))}
                >
                  {analysisReportList.map((r) => (
                    <option key={r.id} value={r.id}>
                      {r.created_at ? new Date(r.created_at).toLocaleString() : `报告 #${r.id}`}
                    </option>
                  ))}
                </select>
                <button
                  className="analysis-new-btn"
                  onClick={handleGenerateNewReport}
                  disabled={analyzingRoom}
                >
                  {analyzingRoom ? '生成中...' : '+ 新报告'}
                </button>
              </div>
            )}
            {analysisReportList.length <= 1 && (
              <div className="analysis-report-selector">
                <span className="analysis-report-date">
                  {analysisResult.created_at ? new Date(analysisResult.created_at).toLocaleString() : ''}
                </span>
                <button
                  className="analysis-new-btn"
                  onClick={handleGenerateNewReport}
                  disabled={analyzingRoom}
                >
                  {analyzingRoom ? '生成中...' : '重新分析'}
                </button>
              </div>
            )}

            <p className="analysis-summary">{analysisResult.summary}</p>

            {/* Resistance ranking cards */}
            {analysisResult.content.resistance_ranking.length > 0 && (
              <div className="analysis-section">
                <h4>阻力排名</h4>
                <div className="analysis-cards">
                  {analysisResult.content.resistance_ranking.map((item, i) => {
                    const hasLinks = item.message_indices && item.message_indices.length > 0 && analysisResult.content.message_id_map
                    return (
                      <div key={i} className={`analysis-card${hasLinks ? ' clickable' : ''}`}
                        onClick={() => hasLinks && handleScrollToMessage(item.message_indices, analysisResult.content.message_id_map)}
                      >
                        <div className="analysis-card-header">
                          <span className="analysis-card-name">{item.persona_name}</span>
                          <span className={`analysis-card-score ${item.score >= 0 ? 'positive' : 'negative'}`}>
                            {item.score > 0 ? '+' : ''}{item.score}
                          </span>
                        </div>
                        <div className="analysis-card-body">{item.reason}</div>
                        {hasLinks && (
                          <div className="analysis-card-link">点击查看对话原文 →</div>
                        )}
                      </div>
                    )
                  })}
                </div>
              </div>
            )}

            {/* Effective arguments cards */}
            {analysisResult.content.effective_arguments.length > 0 && (
              <div className="analysis-section">
                <h4>有效论点</h4>
                <div className="analysis-cards">
                  {analysisResult.content.effective_arguments.map((item, i) => {
                    const hasLinks = item.message_indices && item.message_indices.length > 0 && analysisResult.content.message_id_map
                    return (
                      <div key={i} className={`analysis-card argument${hasLinks ? ' clickable' : ''}`}
                        onClick={() => hasLinks && handleScrollToMessage(item.message_indices, analysisResult.content.message_id_map)}
                      >
                        <div className="analysis-card-header">
                          <span className="analysis-card-argument">{item.argument}</span>
                          <span className="analysis-card-target">→ {item.target_persona}</span>
                        </div>
                        <div className="analysis-card-body">{item.effectiveness}</div>
                        {hasLinks && (
                          <div className="analysis-card-link">点击查看对话原文 →</div>
                        )}
                      </div>
                    )
                  })}
                </div>
              </div>
            )}

            {/* Communication suggestions */}
            {analysisResult.content.communication_suggestions.length > 0 && (
              <div className="analysis-section">
                <h4>沟通建议</h4>
                <div className="analysis-cards">
                  {analysisResult.content.communication_suggestions.map((item, i) => (
                    <div key={i} className="analysis-card suggestion">
                      <div className="analysis-card-header">
                        <span className="analysis-card-name">{item.persona_name}</span>
                        <span className={`suggestion-priority ${item.priority}`}>{item.priority}</span>
                      </div>
                      <div className="analysis-card-body">{item.suggestion}</div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

export default App
