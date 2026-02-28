import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { listOrders, searchNearbyTruckers, acceptAssignment } from '../../services/api'
import { MapContainer, TileLayer, Marker, Popup, Polyline } from 'react-leaflet'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { Button } from '../../components/Button'
import { GradeBadge } from '../../components/Badge'

delete (L.Icon.Default.prototype as unknown as Record<string, unknown>)._getIconUrl
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
  iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
  shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
})

interface Assignment {
  id: string
  order_id: string
  middleman_id: string
  agreed_fee_cents?: number
  estimated_distance_km?: number
  status: string
}

interface Order {
  id: string
  crop_type: string
  quality_grade?: string
  available_volume_kg: number
  accepted_price?: number
}

// Demo coordinates: Coimbatore (farm) → Chennai (buyer)
const FARM_POS: [number, number] = [11.0168, 76.9558]
const BUYER_POS: [number, number] = [13.0827, 80.2707]

export default function BackhaulPing() {
  const navigate = useNavigate()
  const [assignments, setAssignments] = useState<Assignment[]>([])
  const [orders, setOrders] = useState<Record<string, Order>>({})
  const [loading, setLoading] = useState(true)
  const [actionLoading, setActionLoading] = useState<string | null>(null)

  useEffect(() => {
    // Find LOGISTICS_SEARCH orders and fetch their assignments
    listOrders({ status: 'LOGISTICS_SEARCH' })
      .then(async (r) => {
        const logisticsOrders: Order[] = r.data
        const orderMap: Record<string, Order> = {}
        const allAssignments: Assignment[] = []

        for (const order of logisticsOrders) {
          orderMap[order.id] = order
          try {
            const res = await searchNearbyTruckers(order.id)
            // searchNearbyTruckers returns middleman list, not assignments directly
            // For the demo, show the order itself as an actionable card
            if (res.data.length >= 0) {
              allAssignments.push({
                id: `demo-${order.id}`,
                order_id: order.id,
                middleman_id: '',
                estimated_distance_km: 346,
                status: 'OFFERED',
              })
            }
          } catch { /* skip */ }
        }
        setOrders(orderMap)
        setAssignments(allAssignments)
      })
      .finally(() => setLoading(false))
  }, [])

  const handleAccept = async (assignmentId: string, orderId: string) => {
    setActionLoading(assignmentId)
    try {
      await acceptAssignment(assignmentId)
      navigate(`/trucker/tracking/${orderId}`)
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } }
      alert(e.response?.data?.detail ?? 'Could not accept assignment')
      setActionLoading(null)
    }
  }

  return (
    <div className="min-h-screen bg-[#F5F2ED]">
      <div className="bg-white px-4 py-4 shadow-sm flex items-center gap-3">
        <button onClick={() => navigate('/')} className="text-[#4A6741] text-sm font-medium">← Back</button>
        <div>
          <h1 className="text-xl font-bold text-gray-800">Produce Delivery Routes</h1>
          <p className="text-xs text-gray-500">Matches for your backhaul trip</p>
        </div>
      </div>

      {/* Map overview */}
      <div className="mx-4 mt-4 rounded-2xl overflow-hidden shadow-sm" style={{ height: 200 }}>
        <MapContainer center={[12.0, 78.5]} zoom={6} style={{ height: '100%', width: '100%' }} scrollWheelZoom={false}>
          <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
          <Marker position={FARM_POS}><Popup>🌾 Pickup</Popup></Marker>
          <Marker position={BUYER_POS}><Popup>🏭 Delivery</Popup></Marker>
          <Polyline positions={[FARM_POS, BUYER_POS]} color="#4A6741" weight={3} dashArray="8 4" />
        </MapContainer>
      </div>

      {/* Assignment cards */}
      <div className="px-4 py-4 flex flex-col gap-3">
        {loading && <p className="text-center text-gray-400 py-8">Finding nearby jobs…</p>}
        {!loading && assignments.length === 0 && (
          <p className="text-center text-gray-400 py-8">No backhaul jobs near your route right now.</p>
        )}
        {assignments.map((a) => {
          const order = orders[a.order_id]
          if (!order) return null
          const feeCents = a.agreed_fee_cents ?? (order.accepted_price ? Math.round(order.accepted_price * order.available_volume_kg * 0.2 * 100) : 320000)
          return (
            <div key={a.id} className="bg-white rounded-2xl shadow-sm p-4">
              <div className="flex items-start justify-between gap-2 mb-3">
                <div>
                  <p className="font-semibold text-gray-800">{order.crop_type}</p>
                  {order.quality_grade && <GradeBadge grade={order.quality_grade} />}
                  {order.quality_grade === 'B' && (
                    <p className="text-xs text-green-600 mt-1">✅ Refrigerated truck matches needs</p>
                  )}
                </div>
                <div className="text-right">
                  <p className="font-bold text-amber-700 text-lg">₹{(feeCents / 100).toLocaleString()}</p>
                </div>
              </div>

              <div className="flex gap-4 text-sm text-gray-500 mb-4">
                <span>📍 {a.estimated_distance_km ?? 346} km round trip</span>
                <span>💡 2 drop-off stops</span>
              </div>

              <div className="flex gap-3">
                <Button
                  fullWidth
                  onClick={() => handleAccept(a.id, a.order_id)}
                  disabled={!!actionLoading}
                >
                  {actionLoading === a.id ? 'Accepting…' : 'Accept Trip ✓'}
                </Button>
                <Button variant="secondary" fullWidth>
                  Decline ✗
                </Button>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
