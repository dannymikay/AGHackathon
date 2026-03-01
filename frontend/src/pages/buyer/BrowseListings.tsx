import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { MapContainer, TileLayer, Marker, Popup } from 'react-leaflet'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { listOrders } from '../../services/api'
import { GradeBadge, StatusBadge } from '../../components/Badge'
import { Button } from '../../components/Button'

// Fix Leaflet default icon paths (broken by Vite)
delete (L.Icon.Default.prototype as unknown as Record<string, unknown>)._getIconUrl
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
  iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
  shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
})

interface Order {
  id: string
  crop_type: string
  variety?: string
  total_volume_kg: number
  available_volume_kg: number
  unit_price_asking: number
  status: string
  quality_grade?: string
  requires_cold_chain: boolean
  price_guidance?: {
    grade_a_suggested_price: number
    grade_b_standard_price?: number
    urgency_note?: string
    days_remaining?: number
  }
}

const CROP_FILTERS = ['All', 'Tomato', 'Mango', 'Banana', 'Spinach', 'Onion']

export default function BrowseListings() {
  const navigate = useNavigate()
  const [orders, setOrders] = useState<Order[]>([])
  const [cropFilter, setCropFilter] = useState('All')
  const [coldOnly, setColdOnly] = useState(false)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    const params: Record<string, string> = {}
    if (cropFilter !== 'All') params.crop_type = cropFilter
    // Fetch both LISTED and NEGOTIATING so listings stay visible after first bid
    Promise.all([
      listOrders({ ...params, status: 'LISTED' }),
      listOrders({ ...params, status: 'NEGOTIATING' }),
    ])
      .then(([listed, negotiating]) => {
        setOrders([...listed.data, ...negotiating.data])
      })
      .catch(() => setOrders([]))
      .finally(() => setLoading(false))
  }, [cropFilter])

  const filtered = coldOnly ? orders.filter((o) => o.requires_cold_chain) : orders

  return (
    <div className="min-h-screen bg-[#F5F2ED]">
      {/* Header */}
      <div className="bg-white px-4 py-4 shadow-sm flex items-center gap-3">
        <button onClick={() => navigate('/')} className="text-[#4A6741] font-medium text-sm">← Back</button>
        <h1 className="text-xl font-bold text-gray-800 flex-1">Buyer Listings</h1>
      </div>

      {/* Filter chips */}
      <div className="px-4 py-3 flex gap-2 overflow-x-auto">
        {CROP_FILTERS.map((c) => (
          <button
            key={c}
            onClick={() => setCropFilter(c)}
            className={`flex-shrink-0 rounded-full px-4 py-1.5 text-sm font-medium border transition-colors ${
              cropFilter === c
                ? 'bg-[#4A6741] text-white border-[#4A6741]'
                : 'bg-white text-gray-600 border-gray-200'
            }`}
          >
            {c}
          </button>
        ))}
        <button
          onClick={() => setColdOnly(!coldOnly)}
          className={`flex-shrink-0 rounded-full px-4 py-1.5 text-sm font-medium border transition-colors ${
            coldOnly ? 'bg-blue-600 text-white border-blue-600' : 'bg-white text-gray-600 border-gray-200'
          }`}
        >
          ❄️ Cold Chain
        </button>
      </div>

      {/* Map */}
      <div className="mx-4 rounded-2xl overflow-hidden shadow-sm" style={{ height: 220 }}>
        <MapContainer
          center={[11.0168, 76.9558]}
          zoom={8}
          style={{ height: '100%', width: '100%' }}
          scrollWheelZoom={false}
        >
          <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
          {filtered.map((order, i) => (
            <Marker key={order.id} position={[11.0168 + i * 0.15, 76.9558 + i * 0.1]}>
              <Popup>
                <strong>{order.crop_type}</strong>
                <br />
                {order.available_volume_kg} kg @ ₹{order.unit_price_asking}/kg
                <br />
                <button
                  className="text-[#4A6741] font-semibold mt-1"
                  onClick={() => navigate(`/buyer/bid/${order.id}`)}
                >
                  View / Bid
                </button>
              </Popup>
            </Marker>
          ))}
        </MapContainer>
      </div>

      {/* List */}
      <div className="px-4 py-4 flex flex-col gap-3">
        {loading && <p className="text-center text-gray-400 py-8">Loading listings…</p>}
        {!loading && filtered.length === 0 && (
          <p className="text-center text-gray-400 py-8">No listings found.</p>
        )}
        {filtered.map((order) => (
          <div key={order.id} className="bg-white rounded-2xl shadow-sm p-4 flex gap-4">
            <div className="w-16 h-16 bg-green-50 rounded-xl flex items-center justify-center text-3xl flex-shrink-0">
              🌿
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-start justify-between gap-2">
                <div>
                  <p className="font-semibold text-gray-800">{order.crop_type} {order.variety ? `— ${order.variety}` : ''}</p>
                  <div className="flex items-center gap-2 mt-1">
                    {order.quality_grade && <GradeBadge grade={order.quality_grade} />}
                    <StatusBadge status={order.status} />
                  </div>
                </div>
                <p className="text-[#4A6741] font-bold text-right whitespace-nowrap">₹{order.unit_price_asking}/kg</p>
              </div>
              <p className="text-sm text-gray-500 mt-1">{order.available_volume_kg} kg available</p>
              {order.price_guidance?.urgency_note && (
                <p className="text-xs text-amber-600 mt-1">{order.price_guidance.urgency_note}</p>
              )}
              <div className="mt-3">
                <Button onClick={() => navigate(`/buyer/bid/${order.id}`)}>
                  View / Bid
                </Button>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
