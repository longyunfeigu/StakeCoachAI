import React, { createContext, useContext } from 'react'
import { useChat, type UseChatReturn } from '../hooks/useChat'
import { useVoice, type UseVoiceReturn } from '../hooks/useVoice'
import { useCoaching, type UseCoachingReturn } from '../hooks/useCoaching'
import { useAnalysis, type UseAnalysisReturn } from '../hooks/useAnalysis'

export interface ChatContextType {
  chat: UseChatReturn
  voice: UseVoiceReturn
  coaching: UseCoachingReturn
  analysis: UseAnalysisReturn
}

const ChatContext = createContext<ChatContextType | null>(null)

export function ChatProvider({
  roomId,
  children,
}: {
  roomId: number | null
  children: React.ReactNode
}) {
  const voice = useVoice()

  const chat = useChat(roomId, {
    audioPlayerRef: voice.audioPlayerRef,
  })

  const coaching = useCoaching(roomId)
  const analysis = useAnalysis(roomId)

  return (
    <ChatContext.Provider value={{ chat, voice, coaching, analysis }}>
      {children}
    </ChatContext.Provider>
  )
}

export function useChatContext(): ChatContextType {
  const ctx = useContext(ChatContext)
  if (!ctx) {
    throw new Error('useChatContext must be used inside a ChatProvider')
  }
  return ctx
}

export default ChatContext
