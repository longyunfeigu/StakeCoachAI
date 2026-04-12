import { useState, useCallback } from 'react'
import {
  fetchRoomDetail,
  type ChatRoom,
  type ChatRoomDetail,
} from '../services/api'

export interface UseRoomsReturn {
  rooms: ChatRoom[]
  selectedRoomId: number | null
  selectedRoom: ChatRoomDetail | null
  refreshKey: number
  setSelectedRoomId: (id: number | null) => void
  setSelectedRoom: React.Dispatch<React.SetStateAction<ChatRoomDetail | null>>
  refreshRooms: () => void
  selectRoom: (roomId: number) => Promise<ChatRoomDetail | null>
  handleRoomDeleted: (roomId: number) => void
}

export function useRooms(): UseRoomsReturn {
  const [rooms, setRooms] = useState<ChatRoom[]>([])
  const [selectedRoomId, setSelectedRoomId] = useState<number | null>(null)
  const [selectedRoom, setSelectedRoom] = useState<ChatRoomDetail | null>(null)
  const [refreshKey, setRefreshKey] = useState(0)

  const refreshRooms = useCallback(() => {
    setRefreshKey((k) => k + 1)
  }, [])

  const selectRoom = useCallback(async (roomId: number): Promise<ChatRoomDetail | null> => {
    setSelectedRoomId(roomId)
    try {
      const detail = await fetchRoomDetail(roomId)
      setSelectedRoom(detail)
      return detail
    } catch {
      setSelectedRoom(null)
      return null
    }
  }, [])

  const handleRoomDeleted = useCallback(
    (roomId: number) => {
      if (selectedRoomId === roomId) {
        setSelectedRoomId(null)
        setSelectedRoom(null)
      }
      setRooms((prev) => prev.filter((r) => r.id !== roomId))
    },
    [selectedRoomId],
  )

  return {
    rooms,
    selectedRoomId,
    selectedRoom,
    refreshKey,
    setSelectedRoomId,
    setSelectedRoom,
    refreshRooms,
    selectRoom,
    handleRoomDeleted,
  }
}
