import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { getOrder, submitBid } from '../../services/api'
import { InputField, SelectField } from '../../components/InputField'
import { Button } from '../../components/Button'
import { GradeBadge } from '../../components/Badge'

interface Order {
  id: string
  crop_type: string
  variety?: string
  available_volume_kg: number
  unit_price_asking: number
  quality_grade?: string
  price_guidance?: {
    grade_b_standard_price?: number
    grade_b_urgency_price?: number
    urgency_note?: string
    days_remaining?: number
  }
}

const EXPIRY_OPTIONS = [
  { value: '12', label: '12 hours' },
  { value: '24', label: '24 hours' },
  { value: '48', label: '48 hours' },
]

export default function BidForm() {
  const { orderId } = useParams<{ orderId: string }>()
  const navigate = useNavigate()
  const [order, setOrder] = useState<Order | null>(null)
  const [volume, setVolume] = useState('')
  const [price, setPrice] = useState('')
  const [needsDelivery, setNeedsDelivery] = useState(false)
  const [deliveryAddress, setDeliveryAddress] = useState('')
  const [expiry, setExpiry] = useState('24')
  const [notes, setNotes] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [submitted, setSubmitted] = useState(false)

  useEffect(() => {
    if (!orderId) return
    getOrder(orderId).then((r) => {
      setOrder(r.data)
      setVolume(String(r.data.available_volume_kg))
      setPrice(String(r.data.unit_price_asking))
    })
  }, [orderId])

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await submitBid({
        order_id: orderId!,
        offered_price_per_kg: parseFloat(price),
        volume_kg: parseFloat(volume),
        message: notes || undefined,
      })
      setSubmitted(true)
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } }
      setError(e.response?.data?.detail ?? 'Failed to submit bid')
    } finally {
      setLoading(false)
    }
  }

  if (submitted) {
    return (
      <div className="min-h-screen bg-[#F5F2ED] flex items-center justify-center px-4">
        <div className="bg-white rounded-2xl shadow-sm p-8 max-w-sm w-full text-center">
          <div className="text-5xl mb-4">✅</div>
          <h2 className="text-xl font-bold text-gray-800 mb-2">Bid Submitted!</h2>
          <p className="text-gray-500 text-sm mb-6">
            Your bid is <strong>PENDING</strong>. You'll see a status update when the farmer responds.
          </p>
          <Button fullWidth onClick={() => navigate('/buyer/marketplace')}>Back to Marketplace</Button>
        </div>
      </div>
    )
  }

  if (!order) return <div className="min-h-screen bg-[#F5F2ED] flex items-center justify-center"><p className="text-gray-400">Loading…</p></div>

  return (
    <div className="min-h-screen bg-[#F5F2ED]">
      <div className="bg-white px-4 py-4 shadow-sm flex items-center gap-3">
        <button onClick={() => navigate(-1)} className="text-[#4A6741] font-medium text-sm">← Back</button>
        <h1 className="text-xl font-bold text-gray-800">Submit Bid</h1>
      </div>

      <div className="px-4 py-4">
        {/* Order summary card */}
        <div className="bg-white rounded-2xl shadow-sm p-4 mb-4">
          <p className="text-xs text-gray-400 mb-1">Listing #{order.id.slice(0, 8).toUpperCase()}</p>
          <div className="flex items-center gap-2 mb-1">
            <p className="font-semibold text-gray-800">{order.crop_type} {order.variety ? `— ${order.variety}` : ''}</p>
            {order.quality_grade && <GradeBadge grade={order.quality_grade} />}
          </div>
          <p className="text-[#4A6741] font-bold">₹{order.unit_price_asking}/kg</p>
          <p className="text-sm text-gray-500">{order.available_volume_kg} kg available</p>
          {order.price_guidance?.urgency_note && (
            <p className="text-xs text-amber-600 mt-2">{order.price_guidance.urgency_note}</p>
          )}
        </div>

        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <InputField
            label={`Volume Requested (kg) — max ${order.available_volume_kg}`}
            id="volume" type="number" min="1" max={order.available_volume_kg}
            value={volume} onChange={(e) => setVolume(e.target.value)} required
          />
          <InputField
            label="Bid Price per kg (₹)"
            id="price" type="number" step="0.01" min="0"
            value={price} onChange={(e) => setPrice(e.target.value)} required
          />
          {order.price_guidance?.grade_b_standard_price && (
            <p className="text-xs text-gray-500 -mt-2">
              Grade B benchmark: ₹{order.price_guidance.grade_b_standard_price}/kg
            </p>
          )}

          {/* Pickup or Delivery toggle */}
          <div className="flex gap-3">
            <button type="button"
              onClick={() => setNeedsDelivery(false)}
              className={`flex-1 rounded-xl py-2.5 text-sm font-medium border transition-colors ${!needsDelivery ? 'bg-[#4A6741] text-white border-[#4A6741]' : 'bg-white text-gray-600 border-gray-200'}`}
            >
              I will pick up
            </button>
            <button type="button"
              onClick={() => setNeedsDelivery(true)}
              className={`flex-1 rounded-xl py-2.5 text-sm font-medium border transition-colors ${needsDelivery ? 'bg-[#4A6741] text-white border-[#4A6741]' : 'bg-white text-gray-600 border-gray-200'}`}
            >
              I need delivery
            </button>
          </div>

          {needsDelivery && (
            <InputField label="Delivery Address" id="delivery"
              value={deliveryAddress} onChange={(e) => setDeliveryAddress(e.target.value)} />
          )}

          <SelectField label="Bid Expiry" id="expiry" options={EXPIRY_OPTIONS}
            value={expiry} onChange={(e) => setExpiry(e.target.value)} />

          <div className="flex flex-col gap-1">
            <label htmlFor="notes" className="text-sm font-medium text-gray-700">Notes (optional)</label>
            <textarea id="notes" rows={3}
              className="rounded-xl border border-gray-200 bg-white px-4 py-3 text-sm focus:border-[#4A6741] focus:outline-none"
              placeholder="Quality requirements or special instructions"
              value={notes} onChange={(e) => setNotes(e.target.value)}
            />
          </div>

          {error && <p className="text-red-600 text-sm">{error}</p>}

          <Button type="submit" fullWidth disabled={loading}>
            {loading ? 'Submitting…' : 'Submit Bid'}
          </Button>
          <p className="text-xs text-center text-gray-400">
            Deposit will be captured to escrow when the farmer accepts
          </p>
        </form>
      </div>
    </div>
  )
}
