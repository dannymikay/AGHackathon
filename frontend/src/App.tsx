import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider, useAuth } from './context/AuthContext'
import RoleSelection from './pages/RoleSelection'

// Farmer
import FarmerLogin from './pages/farmer/FarmerLogin'
import FarmerDashboard from './pages/farmer/FarmerDashboard'
import HarvestListing from './pages/farmer/HarvestListing'

// Buyer
import BuyerLogin from './pages/buyer/BuyerLogin'
import BrowseListings from './pages/buyer/BrowseListings'
import BidForm from './pages/buyer/BidForm'
import BuyerDashboard from './pages/buyer/BuyerDashboard'

// Trucker
import TruckerLogin from './pages/trucker/TruckerLogin'
import BackhaulPing from './pages/trucker/BackhaulPing'
import ActiveRoute from './pages/trucker/ActiveRoute'

function RequireAuth({ role, children }: { role: string; children: React.ReactNode }) {
  const { token, role: userRole } = useAuth()
  if (!token || userRole !== role) return <Navigate to="/" replace />
  return <>{children}</>
}

function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<RoleSelection />} />

      {/* Farmer */}
      <Route path="/farmer/login" element={<FarmerLogin />} />
      <Route path="/farmer/dashboard" element={
        <RequireAuth role="farmer"><FarmerDashboard /></RequireAuth>
      } />
      <Route path="/farmer/new-listing" element={
        <RequireAuth role="farmer"><HarvestListing /></RequireAuth>
      } />

      {/* Buyer */}
      <Route path="/buyer/login" element={<BuyerLogin />} />
      <Route path="/buyer/marketplace" element={<BrowseListings />} />
      <Route path="/buyer/bid/:orderId" element={
        <RequireAuth role="buyer"><BidForm /></RequireAuth>
      } />
      <Route path="/buyer/dashboard" element={
        <RequireAuth role="buyer"><BuyerDashboard /></RequireAuth>
      } />

      {/* Trucker */}
      <Route path="/trucker/login" element={<TruckerLogin />} />
      <Route path="/trucker/routes" element={
        <RequireAuth role="trucker"><BackhaulPing /></RequireAuth>
      } />
      <Route path="/trucker/tracking/:orderId" element={
        <RequireAuth role="trucker"><ActiveRoute /></RequireAuth>
      } />

      {/* Fallback */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <AppRoutes />
      </BrowserRouter>
    </AuthProvider>
  )
}
