import { useEffect, useState } from 'react'
import {
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
  updatePersona,
  type Organization,
  type Team,
  type PersonaRelationship,
  type PersonaSummary,
} from '../services/api'
import './OrganizationDialog.css'

interface OrganizationDialogProps {
  open: boolean
  onClose: () => void
  onOrgChanged: () => void
  personas: PersonaSummary[]
}

const REL_LABELS: Record<string, string> = {
  superior: '上级',
  subordinate: '下级',
  peer: '同级',
  cross_department: '跨部门',
}

export default function OrganizationDialog({ open, onClose, onOrgChanged, personas }: OrganizationDialogProps) {
  const [orgs, setOrgs] = useState<Organization[]>([])
  const [selectedOrg, setSelectedOrg] = useState<Organization | null>(null)
  const [teams, setTeams] = useState<Team[]>([])
  const [relationships, setRelationships] = useState<PersonaRelationship[]>([])
  const [tab, setTab] = useState<'info' | 'teams' | 'relationships'>('info')

  // Form state for org info
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
    if (open) {
      loadOrgs()
      setError(null)
      setTab('info')
    }
  }, [open])

  // Auto-load first org
  useEffect(() => {
    if (orgs.length > 0 && !selectedOrg) {
      loadOrgDetail(orgs[0].id)
    }
  }, [orgs])

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
      onOrgChanged()
    } catch (e: any) {
      setError(e.message)
    } finally {
      setSaving(false)
    }
  }

  const handleDeleteOrg = async () => {
    if (!selectedOrg || !confirm(`确定删除组织「${selectedOrg.name}」？`)) return
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
      onOrgChanged()
    } catch (e: any) {
      setError(e.message)
    }
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

  // Personas available to add to a team: either in this org without a team, or not in any org
  const assignedTeamIds = new Set(teams.map((t) => t.id))
  const unassignedPersonas = selectedOrg
    ? personas.filter((p) =>
        !p.team_id || !assignedTeamIds.has(p.team_id)
      ).filter((p) => p.id !== 'TEMPLATE')
    : []

  const handleAssignToTeam = async (personaId: string, teamId: number) => {
    if (!selectedOrg) return
    try {
      await updatePersona(personaId, { organization_id: selectedOrg.id, team_id: teamId })
      onOrgChanged()
    } catch (e: any) {
      setError(e.message)
    }
  }

  const handleRemoveFromTeam = async (personaId: string) => {
    if (!selectedOrg) return
    try {
      await updatePersona(personaId, { team_id: null })
      onOrgChanged()
    } catch (e: any) {
      setError(e.message)
    }
  }

  const personaName = (pid: string) => personas.find((p) => p.id === pid)?.name || pid

  if (!open) return null

  return (
    <div className="dialog-overlay" onClick={onClose}>
      <div className="dialog org-dialog" onClick={(e) => e.stopPropagation()}>
        <h3>{selectedOrg ? '编辑组织' : '创建组织'}</h3>

        <div className="dialog-body" style={{ paddingBottom: 0 }}>
          {/* Org selector if multiple */}
          {orgs.length > 1 && (
            <select
              className="org-selector"
              value={selectedOrg?.id ?? ''}
              onChange={(e) => e.target.value && loadOrgDetail(Number(e.target.value))}
            >
              {orgs.map((o) => (
                <option key={o.id} value={o.id}>{o.name}</option>
              ))}
            </select>
          )}
        </div>

        <div className="org-tabs">
          <button className={`org-tab ${tab === 'info' ? 'active' : ''}`} onClick={() => setTab('info')}>基本信息</button>
          <button className={`org-tab ${tab === 'teams' ? 'active' : ''}`} onClick={() => setTab('teams')} disabled={!selectedOrg}>团队</button>
          <button className={`org-tab ${tab === 'relationships' ? 'active' : ''}`} onClick={() => setTab('relationships')} disabled={!selectedOrg}>角色关系</button>
        </div>

        <div className="dialog-body org-tab-content">
          {tab === 'info' && (
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
            </>
          )}

          {tab === 'teams' && selectedOrg && (
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

              {/* Unassigned personas */}
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

          {tab === 'relationships' && selectedOrg && (
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
                        {r.description && <span style={{ color: 'var(--text-muted)', marginLeft: 6 }}>— {r.description}</span>}
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

          {error && <div className="dialog-error">{error}</div>}
        </div>

        <div className="dialog-actions">
          {selectedOrg && (
            <button className="btn-delete" onClick={handleDeleteOrg}>删除组织</button>
          )}
          <button className="btn-cancel" onClick={onClose}>关闭</button>
          {tab === 'info' && (
            <button className="btn-submit" onClick={handleSaveOrg} disabled={saving || !orgName.trim()}>
              {saving ? '保存中...' : '保存'}
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
