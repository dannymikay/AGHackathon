import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { MapContainer, TileLayer, Marker, Popup, Polyline } from 'react-leaflet'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { verifyPickup, verifyDelivery } from '../../services/api'
import { Button } from '../../components/Button'
import { useWebSocket } from '../../hooks/useWebSocket'
import { useAuth } from '../../context/AuthContext'

delete (L.Icon.Default.prototype as unknown as Record<string, unknown>)._getIconUrl
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
  iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
  shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
})

const FARM_POS: [number, number] = [11.0168, 76.9558]
const BUYER_POS: [number, number] = [13.0827, 80.2707]
const TRUCKER_POS: [number, number] = [12.1, 78.2]

export default function ActiveRoute() {
  const { orderId } = useParams<{ orderId: string }>()
  const navigate = useNavigate()
  const { token } = useAuth()
  const { orderStatus } = useWebSocket(orderId ?? null, token)

  const [pickupToken, setPickupToken] = useState('')
  const [deliveryToken, setDeliveryToken] = useState('')
  const [showPickupInput, setShowPickupInput] = useState(false)
  const [showDeliveryInput, setShowDeliveryInput] = useState(false)
  const [message, setMessage] = useState('')
  const [loading, setLoading] = useState(false)

  const TRUCKER_LOCATION = { latitude: TRUCKER_POS[0], longitude: TRUCKER_POS[1] }

  const handlePickup = async () => {
    if (!orderId || !pickupToken) return
    setLoading(true)
    try {
      await verifyPickup({ order_id: orderId, qr_token: pickupToken, middleman_location: TRUCKER_LOCATION })
      setMessage('✅ Pickup confirmed! 20% released to farmer.')
      setShowPickupInput(false)
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } }
      setMessage(`❌ ${e.response?.data?.detail ?? 'Invalid QR token'}`)
    } finally { setLoading(false) }
  }

  const handleDelivery = async () => {
    if (!orderId || !deliveryToken) return
    setLoading(true)
    try {
      await verifyDelivery({ order_id: orderId, qr_token: deliveryToken, middleman_location: TRUCKER_LOCATION })
      setMessage('✅ Delivery confirmed! Remaining funds released.')
      setShowDeliveryInput(false)
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } }
      setMessage(`❌ ${e.response?.data?.detail ?? 'Invalid QR token'}`)
    } finally { setLoading(false) }
  }

  return (
    <div className="min-h-screen bg-[#F5F2ED]">
      <div className="bg-white px-4 py-4 shadow-sm flex items-center gap-3">
        <button onClick={() => navigate(-1)} className="text-[#4A6741] text-sm font-medium">← Back</button>
        <div>
          <h1 className="text-xl font-bold text-gray-800">Delivery Tracking</h1>
          <p className="text-xs text-gray-500">Produce was picked up from farm.</p>
        </div>
      </div>

      {/* Live Map */}
      <div className="mx-4 mt-4 rounded-2xl overflow-hidden shadow-sm" style={{ height: 260 }}>
        <MapContainer center={[12.0, 78.5]} zoom={6} style={{ height: '100%', width: '100%' }} scrollWheelZoom={false}>
          <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
          <Marker position={FARM_POS}><Popup>🌾 Farm — Pickup</Popup></Marker>
          <Marker position={BUYER_POS}><Popup>🏭 Buyer — Delivery</Popup></Marker>
          <Marker position={TRUCKER_POS}><Popup>🚛 Your Location</Popup></Marker>
          <Polyline positions={[FARM_POS, TRUCKER_POS, BUYER_POS]} color="#4A6741" weight={3} />
        </MapContainer>
      </div>

      <div className="px-4 py-4 flex flex-col gap-4">
        {/* Status from WebSocket */}
        {orderStatus && (
          <div className="bg-purple-50 border border-purple-200 rounded-2xl px-4 py-3">
            <p className="text-sm font-semibold text-purple-800">Live Status: {orderStatus.replace('_', ' ')}</p>
          </div>
        )}

        {/* ETA Banner */}
        <div className="bg-amber-50 border border-amber-200 rounded-2xl px-4 py-3 flex items-center justify-between">
          <p className="text-sm text-amber-800 font-medium">ETA to delivery</p>
          <p className="text-lg font-bold text-amber-700">~4 hrs 20 min</p>
        </div>

        {/* Journey steps */}
        <div className="bg-white rounded-2xl shadow-sm p-4">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-6 h-6 rounded-full bg-[#4A6741] text-white flex items-center justify-center text-xs">✓</div>
            <p className="text-sm font-medium text-gray-400 line-through">Picked up — Farm</p>
          </div>
          <div className="ml-3 border-l-2 border-dashed border-gray-200 pl-3 py-1 mb-3">
            <p className="text-xs text-[#4A6741] font-semibold uppercase tracking-wide">IN TRANSIT</p>
          </div>
          <div className="flex items-center gap-3">
            <div className="w-6 h-6 rounded-full bg-blue-100 text-blue-700 flex items-center justify-center text-xs font-bold">B</div>
            <p className="text-sm font-medium text-gray-700">Drop off — Buyer</p>
          </div>
        </div>

        {/* QR Actions */}
        <div className="flex flex-col gap-3">
          <div className="bg-white rounded-2xl shadow-sm p-4">
            <p className="font-semibold text-gray-700 mb-2">🌾 Pickup QR Scan</p>
            <p className="text-xs text-gray-500 mb-3">Enter the farmer's QR token to release 20% payment</p>
            {!showPickupInput ? (
              <Button variant="secondary" fullWidth onClick={() => setShowPickupInput(true)}>
                Scan Pickup QR
              </Button>
            ) : (
              <div className="flex gap-2">
                <input
                  className="flex-1 rounded-xl border border-gray-200 px-3 py-2 text-sm focus:outline-none focus:border-[#4A6741]"
                  placeholder="Paste QR token…"
                  value={pickupToken}
                  onChange={(e) => setPickupToken(e.target.value)}
                />
                <Button onClick={handlePickup} disabled={loading || !pickupToken}>Verify</Button>
              </div>
            )}
          </div>

          <div className="bg-white rounded-2xl shadow-sm p-4">
            <p className="font-semibold text-gray-700 mb-2">🏭 Delivery QR Scan</p>
            <p className="text-xs text-gray-500 mb-3">Enter the buyer's QR token to release final payment</p>
            {!showDeliveryInput ? (
              <Button variant="secondary" fullWidth onClick={() => setShowDeliveryInput(true)}>
                Scan Delivery QR
              </Button>
            ) : (
              <div className="flex gap-2">
                <input
                  className="flex-1 rounded-xl border border-gray-200 px-3 py-2 text-sm focus:outline-none focus:border-[#4A6741]"
                  placeholder="Paste QR token…"
                  value={deliveryToken}
                  onChange={(e) => setDeliveryToken(e.target.value)}
                />
                <Button onClick={handleDelivery} disabled={loading || !deliveryToken}>Verify</Button>
              </div>
            )}
          </div>
        </div>

        {message && (
          <div className={`rounded-2xl p-4 text-sm font-medium ${message.startsWith('✅') ? 'bg-green-50 text-green-800' : 'bg-red-50 text-red-700'}`}>
            {message}
          </div>
        )}
      </div>
    </div>
  )
}
