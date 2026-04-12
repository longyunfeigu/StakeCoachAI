import { useState } from 'react'
import { Routes, Route, useNavigate } from 'react-router-dom'
import Layout from './components/layout/Layout'
import HomePage from './pages/HomePage'
import ChatPage from './pages/ChatPage'
import BattlePrepPage from './pages/BattlePrepPage'
import GrowthPage from './pages/GrowthPage'
import { AppProvider, useAppContext } from './contexts/AppContext'
import { MessageCircle, Layers, Plus, Building2, TrendingUp, Zap } from 'lucide-react'
import './App.css'
import Avatar from './components/Avatar'
import RoomList from './components/RoomList'
import CreateRoomDialog from './components/CreateRoomDialog'
import PersonaEditorDialog from './components/PersonaEditorDialog'
import ScenarioDialog from './components/ScenarioDialog'
import OrganizationDialog from './components/OrganizationDialog'
import type { PersonaSummary } from './services/api'

/**
 * AppInner — legacy shell for routes that have NOT yet been migrated
 * to dedicated page components (e.g. GrowthDashboard, persona editor).
 * Chat functionality is now handled entirely by ChatPage.
 */
function AppInner() {
  const { personaMap, currentOrg, reloadPersonas, reloadOrganizations } = useAppContext()
  const navigate = useNavigate()

  const [selectedRoomId, setSelectedRoomId] = useState<number | null>(null)
  const [showCreateDialog, setShowCreateDialog] = useState(false)
  const [showScenarioDialog, setShowScenarioDialog] = useState(false)
  const [showOrgDialog, setShowOrgDialog] = useState(false)
  const [personaEditorState, setPersonaEditorState] = useState<{
    open: boolean
    persona: PersonaSummary | null
  }>({ open: false, persona: null })
  const [refreshKey, setRefreshKey] = useState(0)

  const loadPersonas = reloadPersonas
  const loadOrg = reloadOrganizations

  const handleRoomCreated = async (roomId: number) => {
    setRefreshKey((k) => k + 1)
    setSelectedRoomId(roomId)
  }

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
          onSelectRoom={(room) => {
            setSelectedRoomId(room.id)
          }}
          onCreateRoom={() => setShowCreateDialog(true)}
          onRoomDeleted={(id) => {
            if (selectedRoomId === id) {
              setSelectedRoomId(null)
            }
          }}
          refreshKey={refreshKey}
        />

        <button
          className="battle-prep-btn"
          onClick={() => navigate('/battle-prep')}
        >
          <Zap size={16} />
          <span>紧急备战</span>
        </button>

        {/* Growth tab button */}
        <button
          className="growth-btn"
          onClick={() => navigate('/growth')}
        >
          <TrendingUp size={16} />
          <span>成长轨迹</span>
        </button>
      </aside>
      <main className="main-content">
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
      </main>

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
    </div>
  )
}

function App() {
  return (
    <AppProvider>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<HomePage />} />
          <Route path="chat" element={<ChatPage />} />
          <Route path="chat/:roomId" element={<ChatPage />} />
          <Route path="battle-prep" element={<BattlePrepPage />} />
          <Route path="growth" element={<GrowthPage />} />
          <Route path="*" element={<AppInner />} />
        </Route>
      </Routes>
    </AppProvider>
  )
}

export default App
