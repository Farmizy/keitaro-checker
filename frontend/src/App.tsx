import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { AuthProvider, useAuth } from "@/hooks/useAuth"
import { AppLayout } from "@/components/layout/AppLayout"
import LoginPage from "@/pages/LoginPage"
import DashboardPage from "@/pages/DashboardPage"
import AccountsPage from "@/pages/AccountsPage"
import CampaignsPage from "@/pages/CampaignsPage"
import RulesPage from "@/pages/RulesPage"
import LogsPage from "@/pages/LogsPage"
import SettingsPage from "@/pages/SettingsPage"
import GeneratorPage from "@/pages/GeneratorPage"
import type { ReactNode } from "react"

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: 1, staleTime: 10_000 },
  },
})

function ProtectedRoute({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth()
  if (loading) return null
  if (!user) return <Navigate to="/login" replace />
  return children
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route
              element={
                <ProtectedRoute>
                  <AppLayout />
                </ProtectedRoute>
              }
            >
              <Route index element={<DashboardPage />} />
              <Route path="accounts" element={<AccountsPage />} />
              <Route path="campaigns" element={<CampaignsPage />} />
              <Route path="rules" element={<RulesPage />} />
              <Route path="logs" element={<LogsPage />} />
              <Route path="settings" element={<SettingsPage />} />
              <Route path="generator" element={<GeneratorPage />} />
            </Route>
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </QueryClientProvider>
  )
}
