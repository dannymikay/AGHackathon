import { useNavigate } from 'react-router-dom'
import { Button } from '../../components/Button'

const STATUS_INFO: Record<string, { label: string; color: string; action?: string }> = {
  PENDING:             { label: 'Waiting for farmer to accept', color: 'bg-yellow-50 border-yellow-200 text-yellow-800' },
  AWAITING_LOGISTICS:  { label: 'Farmer accepted — finding trucker', color: 'bg-orange-50 border-orange-200 text-orange-800' },
  LOCKED:              { label: 'Trucker confirmed — escrow held', color: 'bg-purple-50 border-purple-200 text-purple-800', action: 'Prepare for delivery' },
  IN_TRANSIT:          { label: 'Produce picked up — en route', color: 'bg-blue-50 border-blue-200 text-blue-800', action: 'Prepare for delivery' },
  COMPLETED:           { label: 'Delivered — scan QR to release payment', color: 'bg-green-50 border-green-200 text-green-800', action: 'Scan QR Code' },
  CANCELLED:           { label: '48hr timeout — full refund issued', color: 'bg-red-50 border-red-200 text-red-700' },
}

export default function BuyerDashboard() {
  const navigate = useNavigate()
  // In a real flow, the active order ID would come from navigation state or context
  const activeStatus = 'PENDING'
  const info = STATUS_INFO[activeStatus]

  return (
    <div className="min-h-screen bg-[#F5F2ED]">
      <div className="bg-white px-4 py-4 shadow-sm flex items-center gap-3">
        <button onClick={() => navigate(-1)} className="text-[#4A6741] text-sm font-medium">← Back</button>
        <h1 className="text-xl font-bold text-gray-800">My Orders</h1>
      </div>

      <div className="px-4 py-4 flex flex-col gap-4">
        {/* Live status banner */}
        <div className={`rounded-2xl border p-4 ${info.color}`}>
          <p className="font-semibold">{activeStatus.replace('_', ' ')}</p>
          <p className="text-sm mt-1">{info.label}</p>
          {info.action && (
            <button className="mt-3 underline font-semibold text-sm">{info.action}</button>
          )}
        </div>

        {/* Status timeline */}
        <div className="bg-white rounded-2xl shadow-sm p-4">
          <h2 className="font-semibold text-gray-700 mb-3">Order Progress</h2>
          {Object.entries(STATUS_INFO).map(([status, data]) => {
            const isActive = status === activeStatus
            const isPast = Object.keys(STATUS_INFO).indexOf(status) < Object.keys(STATUS_INFO).indexOf(activeStatus)
            return (
              <div key={status} className="flex items-start gap-3 mb-3">
                <div className={`mt-0.5 w-5 h-5 rounded-full flex-shrink-0 flex items-center justify-center text-xs font-bold ${
                  isPast ? 'bg-[#4A6741] text-white' : isActive ? 'bg-[#4A6741] text-white ring-4 ring-green-200' : 'bg-gray-100 text-gray-400'
                }`}>
                  {isPast ? '✓' : ''}
                </div>
                <div>
                  <p className={`text-sm font-medium ${isActive ? 'text-[#4A6741]' : isPast ? 'text-gray-400 line-through' : 'text-gray-600'}`}>
                    {status.replace('_', ' ')}
                  </p>
                  {isActive && <p className="text-xs text-gray-500">{data.label}</p>}
                </div>
              </div>
            )
          })}
        </div>

        <Button fullWidth onClick={() => navigate('/buyer/marketplace')}>
          Browse More Listings
        </Button>
      </div>
    </div>
  )
}
