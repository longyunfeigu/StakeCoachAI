import React, { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  MessageCircle,
  Plus,
  Activity,
  BarChart3,
  BarChart2,
  GraduationCap,
  Download,
  FileText,
  FileDown,
  Zap,
  Flag,
  Loader2,
} from 'lucide-react'
import { useAppContext } from '../contexts/AppContext'
import { ChatProvider, useChatContext } from '../contexts/ChatContext'
import RoomList from '../components/RoomList'
import CreateRoomDialog from '../components/CreateRoomDialog'
import MessageList from '../components/chat/MessageList'
import ChatInput from '../components/chat/ChatInput'
import ContextPanel from '../components/chat/ContextPanel'
import CoachingPanel from '../components/chat/CoachingPanel'
import AnalysisPanel from '../components/chat/AnalysisPanel'
import EmotionCurve from '../components/EmotionCurve'
import EmotionSidebar from '../components/EmotionSidebar'
import CheatSheetComponent from '../components/CheatSheet'
import {
  exportRoom,
  exportRoomHtml,
  generateCheatSheet,
  type ChatRoom,
  type CheatSheet as CheatSheetData,
} from '../services/api'
import './ChatPage.css'

/* ------------------------------------------------------------------ */
/*  Inner chat area — must be inside ChatProvider                      */
/* ------------------------------------------------------------------ */

function ChatArea() {
  const { personaMap } = useAppContext()
  const { chat, voice, coaching, analysis } = useChatContext()

  const [showEmotionSidebar, setShowEmotionSidebar] = useState(false)
  const [showEmotionCurve, setShowEmotionCurve] = useState(false)
  const [showExportMenu, setShowExportMenu] = useState(false)
  const [showContextPanel, setShowContextPanel] = useState(false)

  // Battle prep state
  const [battlePrepRoundCount, setBattlePrepRoundCount] = useState(0)
  const [battlePrepEnding, setBattlePrepEnding] = useState(false)
  const [cheatSheetData, setCheatSheetData] = useState<CheatSheetData | null>(null)
  const [cheatSheetPersona, setCheatSheetPersona] = useState('')

  // Reset battle prep round count when room changes
  useEffect(() => {
    setBattlePrepRoundCount(0)
  }, [chat.selectedRoom?.room.id])

  const roomPersonas = chat.selectedRoom
    ? chat.selectedRoom.room.persona_ids
        .map((id) => personaMap[id])
        .filter(Boolean)
    : []

  const handleEndBattle = async () => {
    if (!chat.selectedRoom || battlePrepEnding) return
    const personaId = chat.selectedRoom.room.persona_ids[0] || ''
    const persona = personaMap[personaId]
    setCheatSheetPersona(persona?.name || '对方')
    setBattlePrepEnding(true)
    try {
      const sheet = await generateCheatSheet(chat.selectedRoom.room.id)
      setCheatSheetData(sheet)
    } catch (e: any) {
      alert(e?.message || '话术纸条生成失败')
    } finally {
      setBattlePrepEnding(false)
    }
  }

  const handleSend = async () => {
    const success = await chat.handleSend()
    if (!success) return
    // Track battle prep rounds
    if (chat.selectedRoom?.room.type === 'battle_prep') {
      const newCount = battlePrepRoundCount + 1
      setBattlePrepRoundCount(newCount)
      if (newCount >= 12) {
        setTimeout(() => handleEndBattle(), 3000)
      }
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      if (chat.mentionQuery !== null && chat.mentionResults.length > 0) {
        e.preventDefault()
        chat.insertMention(chat.mentionResults[0])
        return
      }
      e.preventDefault()
      handleSend()
    }
  }

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    chat.handleInputChange(
      e,
      personaMap,
      chat.selectedRoom?.room.type,
      chat.selectedRoom?.room.persona_ids,
    )
  }

  const isBattlePrep = chat.selectedRoom?.room.type === 'battle_prep'

  return (
    <>
      <div className="chat-page-center">
      {/* Chat header */}
      <div className="chat-page-header">
        <div className="chat-page-header-left">
          <h3>{chat.selectedRoom?.room.name ?? ''}</h3>
          {chat.selectedRoom && (
            <span className={`room-type-badge ${chat.selectedRoom.room.type}`}>
              {chat.selectedRoom.room.type === 'private'
                ? '私聊'
                : chat.selectedRoom.room.type === 'group'
                  ? '群聊'
                  : '备战'}
            </span>
          )}
        </div>
        <div className="chat-page-header-actions">
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
            onClick={analysis.handleAnalyze}
            title="分析"
            disabled={analysis.analyzingRoom}
          >
            <BarChart2 size={16} />
          </button>
          <button
            className="header-action-btn coaching"
            onClick={() => coaching.handleStartCoaching()}
            title="AI 复盘"
            disabled={coaching.coachingSending}
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
                    exportRoomHtml(chat.selectedRoom!.room.id).catch(console.error)
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
                    exportRoom(chat.selectedRoom!.room.id).catch(console.error)
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

      {/* Battle prep bar */}
      {isBattlePrep && (
        <div className="chat-page-battle-bar">
          <Zap size={14} />
          <span>备战模式 · 第 {battlePrepRoundCount}/12 轮</span>
          <div className="battle-progress">
            <div
              className="battle-progress-fill"
              style={{ width: `${(battlePrepRoundCount / 12) * 100}%` }}
            />
          </div>
          <button
            className="end-battle-btn"
            onClick={handleEndBattle}
            disabled={battlePrepEnding}
          >
            {battlePrepEnding ? (
              <Loader2 size={14} className="spin" />
            ) : (
              <Flag size={14} />
            )}
            {battlePrepEnding ? '生成话术纸条...' : '结束备战'}
          </button>
        </div>
      )}

      {/* Chat body: messages + optional emotion sidebar */}
      <div className="chat-page-chat-with-sidebar">
        <div className="chat-page-chat-column">
          <MessageList
            messages={chat.selectedRoom?.messages ?? []}
            streamingEntries={chat.streamingEntries}
            highlightedMessageId={analysis.highlightedMessageId}
            personaMap={personaMap}
            listRef={chat.messageListRef}
            dispatchSummary={chat.dispatchSummary}
            dispatchExpanded={chat.dispatchExpanded}
            onToggleDispatch={() => chat.setDispatchExpanded((v) => !v)}
            typingPersona={chat.typingPersona}
            playingPersonaId={voice.playingPersonaId}
            onClick={() => showExportMenu && setShowExportMenu(false)}
          />

          <ChatInput
            value={chat.inputValue}
            onInputChange={handleInputChange}
            onKeyDown={handleKeyDown}
            onSend={handleSend}
            sending={chat.sending}
            placeholder={
              chat.selectedRoom?.room.type === 'group'
                ? '输入消息... 使用 @ 提及角色'
                : '输入消息...'
            }
            mentionQuery={chat.mentionQuery}
            mentionResults={chat.mentionResults}
            onInsertMention={chat.insertMention}
            voiceEnabled={voice.voiceEnabled}
            voiceMuted={voice.voiceMuted}
            onToggleVoice={voice.toggleVoice}
            roomId={chat.selectedRoom?.room.id ?? null}
            onVoiceTranscription={(text) => {
              if (!text.trim()) return
              chat.setInputValue('')
              chat.setDispatchSummary(null)
              voice.audioPlayerRef.current?.stop()
              setTimeout(chat.scrollToBottom, 100)
            }}
            onLiveCoachClick={coaching.handleStartLiveCoaching}
            coachingSending={coaching.coachingSending}
          />
        </div>

        {showEmotionSidebar && (
          <EmotionSidebar
            messages={chat.selectedRoom?.messages ?? []}
            personaMap={personaMap}
            onClose={() => setShowEmotionSidebar(false)}
            onExpand={() => setShowEmotionCurve(true)}
          />
        )}
      </div>
      </div>

      {/* Right column: context panel */}
      <ContextPanel
        personas={roomPersonas}
        collapsed={!showContextPanel}
        onToggle={() => setShowContextPanel((v) => !v)}
        onExpandEmotion={() => setShowEmotionCurve(true)}
      />

      {/* Overlay panels */}
      <CoachingPanel
        open={coaching.coachingOpen}
        mode={coaching.coachingMode}
        messages={coaching.coachingMessages}
        streamingContent={coaching.coachingStreaming}
        sending={coaching.coachingSending}
        inputValue={coaching.coachingInput}
        onInputChange={coaching.setCoachingInput}
        onSend={coaching.handleSendCoaching}
        onClose={() => coaching.setCoachingOpen(false)}
        sessionId={coaching.coachingSessionId}
        listRef={coaching.coachingListRef}
      />

      <EmotionCurve
        open={showEmotionCurve}
        onClose={() => setShowEmotionCurve(false)}
        messages={chat.selectedRoom?.messages ?? []}
        personaMap={personaMap}
      />

      {analysis.analysisResult && (
        <AnalysisPanel
          result={analysis.analysisResult}
          reportList={analysis.analysisReportList}
          analyzingRoom={analysis.analyzingRoom}
          onClose={() => analysis.setAnalysisResult(null)}
          onSelectReport={analysis.handleSelectReport}
          onGenerateNewReport={analysis.handleGenerateNewReport}
          onScrollToMessage={analysis.handleScrollToMessage}
        />
      )}

      <CheatSheetComponent
        open={cheatSheetData !== null}
        onClose={() => setCheatSheetData(null)}
        data={cheatSheetData}
        personaName={cheatSheetPersona}
      />
    </>
  )
}

/* ------------------------------------------------------------------ */
/*  ChatPage — top-level page component                                */
/* ------------------------------------------------------------------ */

export default function ChatPage() {
  const { roomId: roomIdParam } = useParams<{ roomId: string }>()
  const navigate = useNavigate()

  const roomId = roomIdParam ? Number(roomIdParam) : null

  const [showCreateDialog, setShowCreateDialog] = useState(false)
  const [refreshKey, setRefreshKey] = useState(0)

  return (
    <div className="chat-page">
      {/* Left column: room list */}
      <div className="chat-page-left">
        <RoomList
          selectedRoomId={roomId}
          onSelectRoom={(room: ChatRoom) => {
            navigate(`/chat/${room.id}`)
          }}
          onCreateRoom={() => setShowCreateDialog(true)}
          onRoomDeleted={(id) => {
            if (roomId === id) {
              navigate('/chat')
            }
          }}
          refreshKey={refreshKey}
        />
      </div>

      {/* Center + Right columns */}
      {roomId ? (
        <ChatProvider roomId={roomId}>
          <ChatAreaWithLoad
            roomId={roomId}
            onRefresh={() => setRefreshKey((k) => k + 1)}
          />
        </ChatProvider>
      ) : (
        <div className="chat-page-empty">
          <div className="chat-page-empty-icon">
            <MessageCircle size={32} strokeWidth={1.5} />
          </div>
          <h2>选择一个对话开始练习</h2>
          <p>从左侧选择聊天室，或创建一个新的对话</p>
          <button
            className="chat-page-empty-cta"
            onClick={() => setShowCreateDialog(true)}
          >
            <Plus size={16} />
            新建聊天室
          </button>
        </div>
      )}

      <CreateRoomDialog
        open={showCreateDialog}
        onClose={() => setShowCreateDialog(false)}
        onCreated={(newRoomId: number) => {
          setRefreshKey((k) => k + 1)
          navigate(`/chat/${newRoomId}`)
        }}
      />
    </div>
  )
}

/* ------------------------------------------------------------------ */
/*  Wrapper that loads room detail on mount / roomId change            */
/* ------------------------------------------------------------------ */

function ChatAreaWithLoad({
  roomId,
}: {
  roomId: number
  onRefresh: () => void
}) {
  const { chat } = useChatContext()

  useEffect(() => {
    chat.loadRoomDetail(roomId)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [roomId])

  // Re-trigger room list refresh after sending a message
  // (The parent refreshKey is bumped via onRefresh, but we also
  // want to refresh when new messages arrive. For now, rely on the
  // RoomList's own fetchRooms triggered by refreshKey.)

  if (!chat.selectedRoom) {
    return (
      <div className="chat-page-empty">
        <div className="chat-page-empty-icon">
          <MessageCircle size={32} strokeWidth={1.5} />
        </div>
        <h2>加载中...</h2>
        <p>正在加载对话内容</p>
      </div>
    )
  }

  return <ChatArea />
}
