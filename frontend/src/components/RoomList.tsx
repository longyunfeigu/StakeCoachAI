import { useEffect, useState } from 'react'
import { MessageSquare, Users, Plus, Trash2 } from 'lucide-react'
import { fetchRooms, deleteRoom, type ChatRoom } from '../services/api'
import './RoomList.css'

interface RoomListProps {
  selectedRoomId: number | null
  onSelectRoom: (room: ChatRoom) => void
  onCreateRoom: () => void
  onRoomDeleted: (roomId: number) => void
  refreshKey: number
}

export default function RoomList({ selectedRoomId, onSelectRoom, onCreateRoom, onRoomDeleted, refreshKey }: RoomListProps) {
  const [rooms, setRooms] = useState<ChatRoom[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setLoading(true)
    fetchRooms()
      .then(setRooms)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [refreshKey])

  const handleDelete = async (e: React.MouseEvent, room: ChatRoom) => {
    e.stopPropagation()
    if (!confirm(`确定删除「${room.name}」？消息将一并删除。`)) return
    try {
      await deleteRoom(room.id)
      setRooms((prev) => prev.filter((r) => r.id !== room.id))
      onRoomDeleted(room.id)
    } catch (err) {
      console.error('Delete failed:', err)
    }
  }

  if (loading) return <div className="room-list"><span className="room-list-loading">加载中...</span></div>
  if (error) return <div className="room-list"><span className="room-list-loading">加载失败</span></div>

  return (
    <div className="room-list">
      <div className="sidebar-section-header">
        <span className="sidebar-section-title">聊天室</span>
        <button className="create-room-btn" onClick={onCreateRoom} title="创建聊天室">
          <Plus size={15} />
        </button>
      </div>
      {rooms.length === 0 ? (
        <div className="room-empty">暂无聊天室</div>
      ) : (
        rooms.map((room) => (
          <div
            key={room.id}
            className={`room-item ${selectedRoomId === room.id ? 'active' : ''}`}
            onClick={() => onSelectRoom(room)}
          >
            <div className="room-item-icon">
              {room.type === 'private' ? <MessageSquare size={16} /> : <Users size={16} />}
            </div>
            <div className="room-info">
              <span className="room-name">{room.name}</span>
              <span className="room-personas">
                {room.persona_ids.join(', ')}
              </span>
            </div>
            <button
              className="room-delete-btn"
              onClick={(e) => handleDelete(e, room)}
              title="删除聊天室"
            >
              <Trash2 size={13} />
            </button>
          </div>
        ))
      )}
    </div>
  )
}
