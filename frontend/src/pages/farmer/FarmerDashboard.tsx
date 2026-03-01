import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { listOrders, listBidsForOrder, acceptBid, rejectBid } from '../../services/api'
import { StatusBadge, GradeBadge } from '../../components/Badge'
import { Button } from '../../components/Button'
import { useAuth } from '../../context/AuthContext'

interface Order { id: string; crop_type: string; variety?: string; status: string; available_volume_kg: number; unit_price_asking: number; quality_grade?: string }
interface Bid { id: string; buyer_id: string; offered_price_per_kg: number; volume_kg: number; status: string; message?: string }

export default function FarmerDashboard() {
  const navigate = useNavigate()
  const { logout, userId } = useAuth()
  const [orders, setOrders] = useState<Order[]>([])
  const [bids, setBids] = useState<Record<string, Bid[]>>({})
  const [bidsError, setBidsError] = useState<Record<string, string>>({})
  const [expandedOrder, setExpandedOrder] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [actionLoading, setActionLoading] = useState<string | null>(null)

  const fetchOrders = () => {
    setLoading(true)
    const params: Record<string, string> = {}
    if (userId) params.farmer_id = userId
    listOrders(params)
      .then((r) => setOrders(r.data))
      .finally(() => setLoading(false))
  }

  useEffect(() => { fetchOrders() }, [])

  const loadBids = async (orderId: string) => {
    if (expandedOrder === orderId) { setExpandedOrder(null); return }
    setExpandedOrder(orderId)
    setBidsError((prev) => { const n = { ...prev }; delete n[orderId]; return n })
    try {
      const r = await listBidsForOrder(orderId)
      setBids((prev) => ({ ...prev, [orderId]: r.data }))
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string }; status?: number } }
      const msg = e.response?.data?.detail ?? `Failed to load bids (HTTP ${e.response?.status ?? 'network error'})`
      setBids((prev) => ({ ...prev, [orderId]: [] }))
      setBidsError((prev) => ({ ...prev, [orderId]: msg }))
    }
  }

  const handleAccept = async (bidId: string) => {
    setActionLoading(bidId)
    try {
      await acceptBid(bidId)
      setExpandedOrder(null)
      setBids({})
      setBidsError({})
      fetchOrders()
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } }
      alert(e.response?.data?.detail ?? 'Error accepting bid')
    } finally { setActionLoading(null) }
  }

  const handleReject = async (bidId: string, orderId: string) => {
    setActionLoading(bidId)
    try {
      await rejectBid(bidId)
      const r = await listBidsForOrder(orderId)
      setBids((prev) => ({ ...prev, [orderId]: r.data }))
    } finally { setActionLoading(null) }
  }

  return (
    <div className="min-h-screen bg-[#F5F2ED]">
      <div className="bg-white px-4 py-4 shadow-sm flex items-center justify-between">
        <h1 className="text-xl font-bold text-gray-800">My Listings</h1>
        <div className="flex gap-2">
          <Button onClick={() => navigate('/farmer/new-listing')}>+ New</Button>
          <Button variant="secondary" onClick={logout}>Sign Out</Button>
        </div>
      </div>

      <div className="px-4 py-4 flex flex-col gap-3">
        {loading && <p className="text-center text-gray-400 py-8">Loading listings…</p>}
        {!loading && orders.length === 0 && (
          <div className="text-center py-12">
            <p className="text-gray-400 mb-4">No listings yet.</p>
            <Button onClick={() => navigate('/farmer/new-listing')}>Create Your First Listing</Button>
          </div>
        )}
        {orders.map((order) => (
          <div key={order.id} className="bg-white rounded-2xl shadow-sm overflow-hidden">
            <div className="p-4">
              <div className="flex items-start justify-between gap-2">
                <div>
                  <p className="font-semibold text-gray-800">{order.crop_type} {order.variety ? `— ${order.variety}` : ''}</p>
                  <div className="flex items-center gap-2 mt-1">
                    <StatusBadge status={order.status} />
                    {order.quality_grade && <GradeBadge grade={order.quality_grade} />}
                  </div>
                </div>
                <p className="text-[#4A6741] font-bold whitespace-nowrap">₹{order.unit_price_asking}/kg</p>
              </div>
              <p className="text-sm text-gray-500 mt-1">{order.available_volume_kg} kg available</p>

              {(order.status === 'NEGOTIATING' || order.status === 'LISTED') && (
                <button
                  className="mt-3 text-sm font-semibold text-[#4A6741] underline"
                  onClick={() => loadBids(order.id)}
                >
                  {expandedOrder === order.id ? 'Hide Bids ▲' : 'View Bids ▼'}
                </button>
              )}
            </div>

            {/* Bid inbox */}
            {expandedOrder === order.id && (
              <div className="border-t border-gray-100 px-4 py-3 bg-gray-50">
                {!bids[order.id] && !bidsError[order.id] && <p className="text-sm text-gray-400">Loading bids…</p>}
                {bidsError[order.id] && (
                  <p className="text-sm text-red-600 mb-2">⚠ {bidsError[order.id]}</p>
                )}
                {bids[order.id]?.length === 0 && !bidsError[order.id] && <p className="text-sm text-gray-400">No bids yet.</p>}
                {bids[order.id]?.map((bid) => (
                  <div key={bid.id} className="flex items-center justify-between py-2 border-b border-gray-100 last:border-0">
                    <div>
                      <p className="text-sm font-medium text-gray-800">₹{bid.offered_price_per_kg}/kg · {bid.volume_kg} kg</p>
                      {bid.message && <p className="text-xs text-gray-500 mt-0.5">{bid.message}</p>}
                      <span className={`text-xs font-semibold ${bid.status === 'PENDING' ? 'text-yellow-600' : bid.status === 'ACCEPTED' ? 'text-green-600' : 'text-red-500'}`}>
                        {bid.status}
                      </span>
                    </div>
                    {bid.status === 'PENDING' && (
                      <div className="flex gap-2">
                        <Button onClick={() => handleAccept(bid.id)} disabled={!!actionLoading}>
                          {actionLoading === bid.id ? '…' : 'Accept'}
                        </Button>
                        <Button variant="danger" onClick={() => handleReject(bid.id, order.id)} disabled={!!actionLoading}>
                          Reject
                        </Button>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
