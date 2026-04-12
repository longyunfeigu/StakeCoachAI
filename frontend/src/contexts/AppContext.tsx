import React, { createContext, useContext, useEffect, useState, useCallback } from 'react'
import {
  fetchPersonas,
  fetchOrganizations,
  fetchScenarios,
  type PersonaSummary,
  type Organization,
  type Scenario,
} from '../services/api'

export interface AppContextValue {
  personaMap: Record<string, PersonaSummary>
  organizations: Organization[]
  currentOrg: Organization | null
  scenarios: Scenario[]
  reloadPersonas: () => void
  reloadOrganizations: () => void
  reloadScenarios: () => void
}

const AppContext = createContext<AppContextValue | null>(null)

export function AppProvider({ children }: { children: React.ReactNode }) {
  const [personaMap, setPersonaMap] = useState<Record<string, PersonaSummary>>({})
  const [organizations, setOrganizations] = useState<Organization[]>([])
  const [currentOrg, setCurrentOrg] = useState<Organization | null>(null)
  const [scenarios, setScenarios] = useState<Scenario[]>([])

  const reloadPersonas = useCallback(() => {
    fetchPersonas()
      .then((personas) => {
        const map: Record<string, PersonaSummary> = {}
        for (const p of personas) {
          map[p.id] = p
        }
        setPersonaMap(map)
      })
      .catch(() => {})
  }, [])

  const reloadOrganizations = useCallback(() => {
    fetchOrganizations()
      .then((orgs) => {
        setOrganizations(orgs)
        if (orgs.length > 0) setCurrentOrg(orgs[0])
        else setCurrentOrg(null)
      })
      .catch(() => {})
  }, [])

  const reloadScenarios = useCallback(() => {
    fetchScenarios()
      .then(setScenarios)
      .catch(() => {})
  }, [])

  useEffect(() => {
    reloadPersonas()
    reloadOrganizations()
    reloadScenarios()
  }, [reloadPersonas, reloadOrganizations, reloadScenarios])

  return (
    <AppContext.Provider
      value={{
        personaMap,
        organizations,
        currentOrg,
        scenarios,
        reloadPersonas,
        reloadOrganizations,
        reloadScenarios,
      }}
    >
      {children}
    </AppContext.Provider>
  )
}

export function useAppContext(): AppContextValue {
  const ctx = useContext(AppContext)
  if (!ctx) {
    throw new Error('useAppContext must be used within an AppProvider')
  }
  return ctx
}

export default AppContext
