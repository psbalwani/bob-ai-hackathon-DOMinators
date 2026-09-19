import type { PropsWithChildren } from "react"
import { Navigate, Route, Routes, useLocation } from "react-router-dom"
import { Layout } from "./components/Layout"
import { TrialOverview } from "./pages/TrialOverview"
import { DrugPerformance } from "./pages/DrugPerformance"
import { AdminOverview } from "./pages/AdminOverview"
import { SiteDrilldown } from "./pages/SiteDrilldown"
import { DeviationDetail } from "./pages/DeviationDetail"
import { CapaView } from "./pages/CapaView"
import { LoginPage } from "./pages/LoginPage"
import { CenteredSpinner } from "./components/Spinner"
import { useAuth } from "./lib/auth"

function ProtectedRoute({ children }: PropsWithChildren) {
  const { isAuthenticated, isLoading } = useAuth()
  const location = useLocation()

  if (isLoading) return <CenteredSpinner />
  if (!isAuthenticated) return <Navigate to="/login" state={{ from: location.pathname }} replace />
  return <>{children}</>
}

export function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        path="/*"
        element={
          <ProtectedRoute>
            <Layout>
              <Routes>
                <Route path="/" element={<TrialOverview />} />
                <Route path="/admin" element={<AdminOverview />} />
                <Route path="/drug-performance" element={<DrugPerformance />} />
                <Route path="/sites/:siteId" element={<SiteDrilldown />} />
                <Route path="/deviations/:deviationId" element={<DeviationDetail />} />
                <Route path="/capa/:capaId" element={<CapaView />} />
              </Routes>
            </Layout>
          </ProtectedRoute>
        }
      />
    </Routes>
  )
}
