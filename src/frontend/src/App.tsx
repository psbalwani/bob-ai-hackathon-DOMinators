import { Route, Routes } from "react-router-dom"
import { Layout } from "./components/Layout"
import { TrialOverview } from "./pages/TrialOverview"
import { SiteDrilldown } from "./pages/SiteDrilldown"
import { DeviationDetail } from "./pages/DeviationDetail"
import { CapaView } from "./pages/CapaView"

export function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<TrialOverview />} />
        <Route path="/sites/:siteId" element={<SiteDrilldown />} />
        <Route path="/deviations/:deviationId" element={<DeviationDetail />} />
        <Route path="/capa/:capaId" element={<CapaView />} />
      </Routes>
    </Layout>
  )
}
