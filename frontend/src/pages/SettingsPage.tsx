import { useCallback, useEffect, useState } from 'react'
import {
  Plus,
  Pencil,
  Trash2,
  Users,
  Layers,
  Building2,
  Volume2,
  Sparkles,
} from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { useAppContext } from '../contexts/AppContext'
import Avatar from '../components/Avatar'
import PersonaEditorDialog from '../components/PersonaEditorDialog'
import {
  updatePersona,
  deletePersona,
  fetchScenarios,
  fetchPersonas,
  createScenario,
  updateScenario,
  deleteScenario,
  fetchOrganizations,
  fetchOrganizationDetail,
  createOrganization,
  updateOrganization,
  deleteOrganization,
  createTeam,
  deleteTeam,
  fetchRelationships,
  createRelationship,
  deleteRelationship,
  type PersonaSummary,
  type Scenario,
  type Organization,
  type Team,
  type PersonaRelationship,
} from '../services/api'
import ConfirmDialog from '../components/layout/ConfirmDialog'
import './SettingsPage.css'

/** Reusable confirm dialog state hook */
function useConfirmDialog() {
  const [state, setState] = useState<{
    open: boolean; title: string; message: string; onConfirm: () => void
  }>({ open: false, title: '', message: '', onConfirm: () => {} })

  const ask = useCallback((title: string, message: string, onConfirm: () => void) => {
    setState({ open: true, title, message, onConfirm })
  }, [])

  const close = useCallback(() => {
    setState((s) => ({ ...s, open: false }))
  }, [])

  const confirm = useCallback(() => {
    state.onConfirm()
    close()
  }, [state.onConfirm, close])

  return { ...state, ask, close, confirm }
}

type TabKey = 'personas' | 'scenarios' | 'organizations' | 'preferences'

const TABS: { key: TabKey; label: string; icon: React.ReactNode }[] = [
  { key: 'personas', label: '角色', icon: <Users size={14} /> },
  { key: 'scenarios', label: '场景', icon: <Layers size={14} /> },
  { key: 'organizations', label: '组织', icon: <Building2 size={14} /> },
  { key: 'preferences', label: '偏好', icon: <Volume2 size={14} /> },
]

// ---------------------------------------------------------------------------
// Personas Tab
// ---------------------------------------------------------------------------

function PersonasTab() {
  const navigate = useNavigate()
  const { personaMap, currentOrg, reloadPersonas } = useAppContext()
  const personas = Object.values(personaMap)
  const dialog = useConfirmDialog()

  const [dialogOpen, setDialogOpen] = useState(false)
  const [editing, setEditing] = useState<PersonaSummary | null>(null)

  const startCreate = () => {
    setEditing(null)
    setDialogOpen(true)
  }

  const startEdit = (persona: PersonaSummary) => {
    setEditing(persona)
    setDialogOpen(true)
  }

  const handleDialogClose = () => {
    setDialogOpen(false)
    setEditing(null)
  }

  const handleSaved = () => {
    reloadPersonas()
  }

  return (
    <>
      <div className="settings-section-header">
        <h3 className="settings-section-title">角色管理</h3>
        <div className="settings-header-actions">
          <button
            className="persona-build-btn"
            onClick={() => navigate('/persona/new')}
            title="粘贴素材让 AI 生成对手画像"
          >
            <Sparkles size={14} />
            从素材生成对手
          </button>
          <button className="settings-create-btn" onClick={startCreate}>
            <Plus size={14} />
            创建新角色
          </button>
        </div>
      </div>

      <div className="settings-list">
        {personas.length === 0 && (
          <div className="settings-empty">
            <div className="settings-empty-icon">
              <Users size={36} />
            </div>
            <p>暂无角色，点击上方按钮创建</p>
          </div>
        )}
        {personas.map((p) => (
          <div
            key={p.id}
            className={`settings-list-item${editing?.id === p.id ? ' selected' : ''}`}
            onClick={() => startEdit(p)}
          >
            <div className="settings-item-avatar">
              <Avatar name={p.name} color={p.avatar_color || '#2D9C6F'} size={40} />
            </div>
            <div className="settings-item-info">
              <div className="settings-item-name">{p.name}</div>
              <div className="settings-item-role">{p.role}</div>
            </div>
            <div className="settings-item-actions">
              <button
                className="settings-item-btn"
                onClick={(e) => { e.stopPropagation(); startEdit(p) }}
                title="编辑"
              >
                <Pencil size={14} />
              </button>
              <button
                className="settings-item-btn danger"
                onClick={(e) => {
                  e.stopPropagation()
                  dialog.ask('删除角色', `确定删除角色「${p.name}」？此操作无法撤销。`, () => {
                    deletePersona(p.id).then(() => reloadPersonas())
                  })
                }}
                title="删除"
              >
                <Trash2 size={14} />
              </button>
            </div>
          </div>
        ))}
      </div>

      <PersonaEditorDialog
        open={dialogOpen}
        onClose={handleDialogClose}
        onSaved={handleSaved}
        editingPersona={editing}
        currentOrg={currentOrg}
      />
      <ConfirmDialog open={dialog.open} title={dialog.title} message={dialog.message} confirmLabel="删除" danger onConfirm={dialog.confirm} onCancel={dialog.close} />
    </>
  )
}

// ---------------------------------------------------------------------------
// Scenarios Tab
// ---------------------------------------------------------------------------

function ScenariosTab() {
  const { personaMap, reloadScenarios } = useAppContext()
  const dialog = useConfirmDialog()

  const [scenarios, setScenarios] = useState<Scenario[]>([])
  const [allPersonas, setAllPersonas] = useState<PersonaSummary[]>([])
  const [editing, setEditing] = useState<Scenario | null>(null)
  const [isNew, setIsNew] = useState(false)

  // Form state
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [contextPrompt, setContextPrompt] = useState('')
  const [suggestedPersonaIds, setSuggestedPersonaIds] = useState<string[]>([])
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  const showForm = isNew || editing !== null

  const loadData = async () => {
    try {
      const [s, p] = await Promise.all([fetchScenarios(), fetchPersonas()])
      setScenarios(s)
      setAllPersonas(p)
    } catch {
      /* ignore */
    }
  }

  useEffect(() => {
    loadData()
  }, [])

  const startCreate = () => {
    setEditing(null)
    setIsNew(true)
    setName('')
    setDescription('')
    setContextPrompt('')
    setSuggestedPersonaIds([])
    setError(null)
  }

  const startEdit = (scenario: Scenario) => {
    setEditing(scenario)
    setIsNew(false)
    setName(scenario.name)
    setDescription(scenario.description)
    setContextPrompt(scenario.context_prompt)
    setSuggestedPersonaIds([...scenario.suggested_persona_ids])
    setError(null)
  }

  const handleCancel = () => {
    setEditing(null)
    setIsNew(false)
    setError(null)
  }

  const togglePersona = (pid: string) => {
    setSuggestedPersonaIds((prev) =>
      prev.includes(pid) ? prev.filter((p) => p !== pid) : [...prev, pid],
    )
  }

  const handleSave = async () => {
    if (!name.trim() || !contextPrompt.trim()) {
      setError('名称和上下文提示词不能为空')
      return
    }
    setSubmitting(true)
    setError(null)
    try {
      if (isNew) {
        await createScenario({
          name: name.trim(),
          description: description.trim(),
          context_prompt: contextPrompt.trim(),
          suggested_persona_ids: suggestedPersonaIds,
        })
      } else if (editing) {
        await updateScenario(editing.id, {
          name: name.trim(),
          description: description.trim(),
          context_prompt: contextPrompt.trim(),
          suggested_persona_ids: suggestedPersonaIds,
        })
      }
      await loadData()
      reloadScenarios()
      handleCancel()
    } catch (e: any) {
      setError(e.message)
    } finally {
      setSubmitting(false)
    }
  }

  const handleDelete = () => {
    if (!editing) return
    dialog.ask('删除场景', `确定删除场景「${editing.name}」？此操作无法撤销。`, async () => {
      setSubmitting(true)
      try {
        await deleteScenario(editing.id)
        await loadData()
        reloadScenarios()
        handleCancel()
      } catch (e: any) {
        setError(e.message)
      } finally {
        setSubmitting(false)
      }
    })
  }

  return (
    <>
      <div className="settings-section-header">
        <h3 className="settings-section-title">场景管理</h3>
        <button className="settings-create-btn" onClick={startCreate}>
          <Plus size={14} />
          新建场景
        </button>
      </div>

      <div className="settings-list">
        {scenarios.length === 0 && !showForm && (
          <div className="settings-empty">
            <div className="settings-empty-icon">
              <Layers size={36} />
            </div>
            <p>暂无场景，点击上方按钮创建</p>
          </div>
        )}
        {scenarios.map((s) => (
          <div
            key={s.id}
            className={`settings-list-item${editing?.id === s.id ? ' selected' : ''}`}
            onClick={() => startEdit(s)}
          >
            <div className="settings-item-info">
              <div className="settings-item-name">{s.name}</div>
              {s.description && (
                <div className="settings-item-desc">{s.description}</div>
              )}
              {s.suggested_persona_ids.length > 0 && (
                <div className="settings-persona-chips">
                  {s.suggested_persona_ids.map((pid) => (
                    <span key={pid} className="settings-persona-chip">
                      {personaMap[pid]?.name || pid}
                    </span>
                  ))}
                </div>
              )}
            </div>
            <div className="settings-item-actions">
              <button
                className="settings-item-btn"
                onClick={(e) => { e.stopPropagation(); startEdit(s) }}
                title="编辑"
              >
                <Pencil size={14} />
              </button>
              <button
                className="settings-item-btn danger"
                onClick={(e) => {
                  e.stopPropagation()
                  dialog.ask('删除场景', `确定删除场景「${s.name}」？此操作无法撤销。`, () => {
                    deleteScenario(s.id).then(() => { loadData(); reloadScenarios() })
                  })
                }}
                title="删除"
              >
                <Trash2 size={14} />
              </button>
            </div>
          </div>
        ))}
      </div>

      {showForm && (
        <div className="settings-form-panel">
          <h4>{isNew ? '新建场景' : '编辑场景'}</h4>

          <label className="field-label">
            名称
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="场景名称"
              autoFocus
            />
          </label>

          <label className="field-label">
            描述（可选）
            <input
              type="text"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="简短描述"
            />
          </label>

          <label className="field-label">
            上下文提示词
            <textarea
              value={contextPrompt}
              onChange={(e) => setContextPrompt(e.target.value)}
              placeholder="设定场景的上下文提示词..."
            />
          </label>

          <div className="field-label" style={{ marginBottom: 4 }}>推荐角色（可选）</div>
          <div className="settings-checkbox-list">
            {allPersonas.map((p) => (
              <label key={p.id} className="settings-checkbox-item">
                <input
                  type="checkbox"
                  checked={suggestedPersonaIds.includes(p.id)}
                  onChange={() => togglePersona(p.id)}
                />
                <span
                  className="settings-checkbox-color"
                  style={{ backgroundColor: p.avatar_color || '#999' }}
                />
                <span>{p.name}</span>
              </label>
            ))}
          </div>

          {error && <div className="settings-error">{error}</div>}

          <div className="settings-form-actions">
            {editing && (
              <button className="btn-delete" onClick={handleDelete} disabled={submitting}>
                删除
              </button>
            )}
            <button className="btn-cancel" onClick={handleCancel}>取消</button>
            <button
              className="btn-submit"
              onClick={handleSave}
              disabled={submitting}
            >
              {submitting ? '保存中...' : '保存'}
            </button>
          </div>
        </div>
      )}
      <ConfirmDialog open={dialog.open} title={dialog.title} message={dialog.message} confirmLabel="删除" danger onConfirm={dialog.confirm} onCancel={dialog.close} />
    </>
  )
}

// ---------------------------------------------------------------------------
// Organizations Tab
// ---------------------------------------------------------------------------

const REL_LABELS: Record<string, string> = {
  superior: '上级',
  subordinate: '下级',
  peer: '同级',
  cross_department: '跨部门',
}

function OrganizationsTab() {
  const { reloadOrganizations, reloadPersonas } = useAppContext()
  const dialog = useConfirmDialog()
  const [personas, setPersonas] = useState<PersonaSummary[]>([])

  const [orgs, setOrgs] = useState<Organization[]>([])
  const [selectedOrg, setSelectedOrg] = useState<Organization | null>(null)
  const [teams, setTeams] = useState<Team[]>([])
  const [relationships, setRelationships] = useState<PersonaRelationship[]>([])
  const [orgTab, setOrgTab] = useState<'info' | 'teams' | 'relationships'>('info')

  // Org form state
  const [orgName, setOrgName] = useState('')
  const [orgIndustry, setOrgIndustry] = useState('')
  const [orgDescription, setOrgDescription] = useState('')
  const [orgContextPrompt, setOrgContextPrompt] = useState('')

  // Team add form
  const [newTeamName, setNewTeamName] = useState('')

  // Relationship add form
  const [relFrom, setRelFrom] = useState('')
  const [relTo, setRelTo] = useState('')
  const [relType, setRelType] = useState('peer')
  const [relDesc, setRelDesc] = useState('')

  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const loadOrgs = () => fetchOrganizations().then(setOrgs).catch(() => {})

  const loadOrgDetail = async (orgId: number) => {
    const detail = await fetchOrganizationDetail(orgId)
    setSelectedOrg(detail.organization)
    setTeams(detail.teams)
    setOrgName(detail.organization.name)
    setOrgIndustry(detail.organization.industry)
    setOrgDescription(detail.organization.description)
    setOrgContextPrompt(detail.organization.context_prompt)
    fetchRelationships(orgId).then(setRelationships).catch(() => {})
  }

  useEffect(() => {
    loadOrgs()
    fetchPersonas().then(setPersonas).catch(() => {})
    setError(null)
  }, [])

  useEffect(() => {
    if (orgs.length > 0 && !selectedOrg) {
      loadOrgDetail(orgs[0].id)
    }
  }, [orgs])

  const handleNewOrg = () => {
    setSelectedOrg(null)
    setTeams([])
    setRelationships([])
    setOrgName('')
    setOrgIndustry('')
    setOrgDescription('')
    setOrgContextPrompt('')
    setOrgTab('info')
    setError(null)
  }

  const handleSaveOrg = async () => {
    setSaving(true)
    setError(null)
    try {
      if (selectedOrg) {
        await updateOrganization(selectedOrg.id, {
          name: orgName,
          industry: orgIndustry,
          description: orgDescription,
          context_prompt: orgContextPrompt,
        })
      } else {
        const created = await createOrganization({
          name: orgName,
          industry: orgIndustry,
          description: orgDescription,
          context_prompt: orgContextPrompt,
        })
        await loadOrgs()
        await loadOrgDetail(created.id)
      }
      reloadOrganizations()
    } catch (e: any) {
      setError(e.message)
    } finally {
      setSaving(false)
    }
  }

  const handleDeleteOrg = () => {
    if (!selectedOrg) return
    dialog.ask('删除组织', `确定删除组织「${selectedOrg.name}」？所有关联的团队和关系数据将一并删除，此操作无法撤销。`, async () => {
      try {
        await deleteOrganization(selectedOrg.id)
        setSelectedOrg(null)
        setTeams([])
        setRelationships([])
        setOrgName('')
        setOrgIndustry('')
        setOrgDescription('')
        setOrgContextPrompt('')
        await loadOrgs()
        reloadOrganizations()
        reloadPersonas()
      } catch (e: any) {
        setError(e.message)
      }
    })
  }

  const handleAddTeam = async () => {
    if (!selectedOrg || !newTeamName.trim()) return
    try {
      await createTeam(selectedOrg.id, { name: newTeamName.trim() })
      setNewTeamName('')
      await loadOrgDetail(selectedOrg.id)
    } catch (e: any) {
      setError(e.message)
    }
  }

  const handleDeleteTeam = async (teamId: number) => {
    if (!selectedOrg) return
    try {
      await deleteTeam(selectedOrg.id, teamId)
      await loadOrgDetail(selectedOrg.id)
    } catch (e: any) {
      setError(e.message)
    }
  }

  const handleAddRelationship = async () => {
    if (!selectedOrg || !relFrom || !relTo || relFrom === relTo) return
    try {
      await createRelationship(selectedOrg.id, {
        from_persona_id: relFrom,
        to_persona_id: relTo,
        relationship_type: relType,
        description: relDesc,
      })
      setRelDesc('')
      fetchRelationships(selectedOrg.id).then(setRelationships)
    } catch (e: any) {
      setError(e.message)
    }
  }

  const handleDeleteRelationship = async (relId: number) => {
    if (!selectedOrg) return
    try {
      await deleteRelationship(selectedOrg.id, relId)
      fetchRelationships(selectedOrg.id).then(setRelationships)
    } catch (e: any) {
      setError(e.message)
    }
  }

  const assignedTeamIds = new Set(teams.map((t) => t.id))
  const unassignedPersonas = selectedOrg
    ? personas.filter((p) =>
        !p.team_id || !assignedTeamIds.has(p.team_id)
      ).filter((p) => p.id !== 'TEMPLATE')
    : []

  const handleAssignToTeam = async (personaId: string, tId: number) => {
    if (!selectedOrg) return
    try {
      await updatePersona(personaId, { organization_id: selectedOrg.id, team_id: tId })
      reloadPersonas()
      fetchPersonas().then(setPersonas).catch(() => {})
    } catch (e: any) {
      setError(e.message)
    }
  }

  const handleRemoveFromTeam = async (personaId: string) => {
    if (!selectedOrg) return
    try {
      await updatePersona(personaId, { team_id: null })
      reloadPersonas()
      fetchPersonas().then(setPersonas).catch(() => {})
    } catch (e: any) {
      setError(e.message)
    }
  }

  const personaName = (pid: string) => personas.find((p) => p.id === pid)?.name || pid

  return (
    <>
      <div className="settings-section-header">
        <h3 className="settings-section-title">组织管理</h3>
        <button className="settings-create-btn" onClick={handleNewOrg}>
          <Plus size={14} />
          新建组织
        </button>
      </div>

      <div className="settings-org-layout">
        {/* Org selector if multiple */}
        {orgs.length > 1 && (
          <select
            className="settings-org-selector"
            value={selectedOrg?.id ?? ''}
            onChange={(e) => e.target.value && loadOrgDetail(Number(e.target.value))}
          >
            {orgs.map((o) => (
              <option key={o.id} value={o.id}>{o.name}</option>
            ))}
          </select>
        )}

        {/* Org sub-tabs */}
        <div className="settings-org-tabs">
          <button className={`settings-org-tab${orgTab === 'info' ? ' active' : ''}`} onClick={() => setOrgTab('info')}>
            基本信息
          </button>
          <button
            className={`settings-org-tab${orgTab === 'teams' ? ' active' : ''}`}
            onClick={() => setOrgTab('teams')}
            disabled={!selectedOrg}
          >
            团队
          </button>
          <button
            className={`settings-org-tab${orgTab === 'relationships' ? ' active' : ''}`}
            onClick={() => setOrgTab('relationships')}
            disabled={!selectedOrg}
          >
            角色关系
          </button>
        </div>

        <div className="settings-form-panel" style={{ marginTop: 0 }}>
          {orgTab === 'info' && (
            <>
              <label className="field-label">
                组织名称
                <input type="text" value={orgName} onChange={(e) => setOrgName(e.target.value)} placeholder="如：Acme Corp" />
              </label>
              <label className="field-label">
                行业
                <input type="text" value={orgIndustry} onChange={(e) => setOrgIndustry(e.target.value)} placeholder="如：SaaS / 金融 / 制造" />
              </label>
              <label className="field-label">
                组织描述
                <textarea value={orgDescription} onChange={(e) => setOrgDescription(e.target.value)} placeholder="组织的业务、产品、文化..." style={{ minHeight: 60 }} />
              </label>
              <label className="field-label">
                上下文提示词
                <textarea value={orgContextPrompt} onChange={(e) => setOrgContextPrompt(e.target.value)} placeholder="注入所有角色 system prompt 的组织背景..." style={{ minHeight: 80 }} />
              </label>

              <div className="settings-form-actions">
                {selectedOrg && (
                  <button className="btn-delete" onClick={handleDeleteOrg}>删除组织</button>
                )}
                <button className="btn-submit" onClick={handleSaveOrg} disabled={saving || !orgName.trim()}>
                  {saving ? '保存中...' : '保存'}
                </button>
              </div>
            </>
          )}

          {orgTab === 'teams' && selectedOrg && (
            <>
              {teams.length > 0 ? (
                <div className="team-list">
                  {teams.map((t) => {
                    const members = personas.filter((p) => p.team_id === t.id)
                    return (
                      <div key={t.id} className="team-item-block">
                        <div className="team-item">
                          <div className="team-item-info">
                            <div className="team-item-name">{t.name}</div>
                            {t.description && <div className="team-item-desc">{t.description}</div>}
                          </div>
                          <button className="team-delete-btn" onClick={() => handleDeleteTeam(t.id)}>删除</button>
                        </div>
                        <div className="team-members">
                          {members.length > 0 ? (
                            members.map((p) => (
                              <span key={p.id} className="team-member-chip">
                                <span className="team-member-dot" style={{ background: p.avatar_color || '#999' }} />
                                {p.name}
                                <button
                                  className="team-member-remove"
                                  onClick={() => handleRemoveFromTeam(p.id)}
                                  title="移出团队"
                                >&times;</button>
                              </span>
                            ))
                          ) : (
                            <span className="team-members-empty">暂无成员</span>
                          )}
                          <select
                            className="team-add-member-select"
                            value=""
                            onChange={(e) => e.target.value && handleAssignToTeam(e.target.value, t.id)}
                          >
                            <option value="">+ 添加角色</option>
                            {unassignedPersonas.map((p) => (
                              <option key={p.id} value={p.id}>{p.name} ({p.role})</option>
                            ))}
                          </select>
                        </div>
                      </div>
                    )
                  })}
                </div>
              ) : (
                <div className="empty-hint">暂无团队，添加第一个</div>
              )}

              {unassignedPersonas.length > 0 && teams.length > 0 && (
                <div style={{ marginTop: 8, fontSize: 12, color: 'var(--text-muted)' }}>
                  未分配团队的角色：{unassignedPersonas.map((p) => p.name).join('、')}
                </div>
              )}

              <div className="add-team-form" style={{ marginTop: 10 }}>
                <input
                  type="text"
                  value={newTeamName}
                  onChange={(e) => setNewTeamName(e.target.value)}
                  placeholder="团队名称"
                  onKeyDown={(e) => e.key === 'Enter' && handleAddTeam()}
                />
                <button onClick={handleAddTeam} disabled={!newTeamName.trim()}>添加团队</button>
              </div>
            </>
          )}

          {orgTab === 'relationships' && selectedOrg && (
            <>
              {relationships.length > 0 ? (
                <div className="rel-list">
                  {relationships.map((r) => (
                    <div key={r.id} className="rel-item">
                      <span>
                        <strong>{personaName(r.from_persona_id)}</strong>
                        <span className={`rel-type-badge ${r.relationship_type}`}>
                          {REL_LABELS[r.relationship_type] || r.relationship_type}
                        </span>
                        <strong>{personaName(r.to_persona_id)}</strong>
                        {r.description && <span style={{ color: 'var(--text-muted)', marginLeft: 6 }}>-- {r.description}</span>}
                      </span>
                      <button className="team-delete-btn" onClick={() => handleDeleteRelationship(r.id)}>删除</button>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="empty-hint">暂无角色关系</div>
              )}
              <div className="add-rel-form">
                <select value={relFrom} onChange={(e) => setRelFrom(e.target.value)}>
                  <option value="">角色A</option>
                  {personas.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
                </select>
                <select value={relType} onChange={(e) => setRelType(e.target.value)}>
                  <option value="superior">上级</option>
                  <option value="subordinate">下级</option>
                  <option value="peer">同级</option>
                  <option value="cross_department">跨部门</option>
                </select>
                <select value={relTo} onChange={(e) => setRelTo(e.target.value)}>
                  <option value="">角色B</option>
                  {personas.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
                </select>
                <input type="text" value={relDesc} onChange={(e) => setRelDesc(e.target.value)} placeholder="描述（可选）" style={{ flex: 1 }} />
                <button onClick={handleAddRelationship} disabled={!relFrom || !relTo || relFrom === relTo}>添加</button>
              </div>
            </>
          )}

          {error && <div className="settings-error">{error}</div>}
        </div>
      </div>
      <ConfirmDialog open={dialog.open} title={dialog.title} message={dialog.message} confirmLabel="删除" danger onConfirm={dialog.confirm} onCancel={dialog.close} />
    </>
  )
}

// ---------------------------------------------------------------------------
// Preferences Tab
// ---------------------------------------------------------------------------

function PreferencesTab() {
  return (
    <div className="settings-placeholder">
      <div className="settings-placeholder-icon">
        <Volume2 size={28} />
      </div>
      <h3>语音设置即将推出</h3>
      <p>TTS 语音合成、角色专属音色等功能正在开发中</p>
    </div>
  )
}

// ---------------------------------------------------------------------------
// SettingsPage
// ---------------------------------------------------------------------------

const SettingsPage: React.FC = () => {
  const [activeTab, setActiveTab] = useState<TabKey>('personas')

  return (
    <div className="settings-page">
      <div className="settings-tab-bar">
        {TABS.map((tab) => (
          <button
            key={tab.key}
            className={`settings-tab${activeTab === tab.key ? ' active' : ''}`}
            onClick={() => setActiveTab(tab.key)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <div className="settings-content">
        {activeTab === 'personas' && <PersonasTab />}
        {activeTab === 'scenarios' && <ScenariosTab />}
        {activeTab === 'organizations' && <OrganizationsTab />}
        {activeTab === 'preferences' && <PreferencesTab />}
      </div>
    </div>
  )
}

export default SettingsPage
