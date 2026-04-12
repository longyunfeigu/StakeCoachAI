import { useEffect, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
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
  const location = useLocation()

  useEffect(() => {
    setLoading(true)
    fetchRooms()
      .then(setRooms)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [refreshKey])

  const handleDelete = async (e: React.MouseEvent, room: ChatRoom) => {
    e.stopPropagation()
    e.preventDefault() // prevent Link navigation
    if (!confirm(`确定删除「${room.name}」？消息将一并删除。`)) return
    try {
      await deleteRoom(room.id)
      setRooms((prev) => prev.filter((r) => r.id !== room.id))
      onRoomDeleted(room.id)
    } catch (err) {
      console.error('Delete failed:', err)
    }
  }

  /** Check if a room is active by URL or by selectedRoomId prop */
  const isActive = (roomId: number) => {
    // Check URL path
    if (location.pathname === `/chat/${roomId}`) return true
    // Fallback to prop-based selection (for current routing setup)
    return selectedRoomId === roomId
  }

  if (loading) return <div className="room-list"><span className="room-list-loading">加载中...</span></div>
  if (error) return <div className="room-list"><span className="room-list-loading">加载失败</span></div>

  const regularRooms = rooms.filter(r => r.type !== 'battle_prep')
  const battleRooms = rooms.filter(r => r.type === 'battle_prep')

  const renderRoom = (room: ChatRoom) => (
    <Link
      key={room.id}
      to={`/chat/${room.id}`}
      className={`room-item ${isActive(room.id) ? 'active' : ''} ${room.type === 'battle_prep' ? 'battle-prep' : ''}`}
      onClick={() => onSelectRoom(room)}
      style={{ textDecoration: 'none', color: 'inherit' }}
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
    </Link>
  )

  return (
    <div className="room-list">
      <div className="sidebar-section-header">
        <span className="sidebar-section-title">聊天室</span>
        <button className="create-room-btn" onClick={onCreateRoom} title="创建聊天室">
          <Plus size={15} />
        </button>
      </div>
      {regularRooms.length === 0 ? (
        <div className="room-empty">
          <p>还没有对话</p>
          <button className="create-room-btn" onClick={onCreateRoom} style={{ margin: '8px auto 0', width: 'auto', padding: '6px 14px', height: 'auto', borderRadius: '6px', fontSize: '12px', display: 'flex', alignItems: 'center', gap: '4px' }}>
            <Plus size={12} /> 新建聊天室
          </button>
        </div>
      ) : (
        regularRooms.map(renderRoom)
      )}
      {battleRooms.length > 0 && (
        <>
          <div className="sidebar-section-header" style={{ marginTop: 12, paddingTop: 10, borderTop: '1px solid var(--border)' }}>
            <span className="sidebar-section-title" style={{ color: 'var(--amber)' }}>备战</span>
          </div>
          {battleRooms.map(renderRoom)}
        </>
      )}
    </div>
  )
}
