import { useState, useRef } from 'react'
import type { FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { createOrder } from '../../services/api'
import { InputField, SelectField } from '../../components/InputField'
import { Button } from '../../components/Button'

const CROP_OPTIONS = [
  { value: 'Tomato', label: 'Tomato' },
  { value: 'Mango', label: 'Mango' },
  { value: 'Banana', label: 'Banana' },
  { value: 'Spinach', label: 'Spinach' },
  { value: 'Onion', label: 'Onion' },
  { value: 'Corn', label: 'Corn' },
  { value: 'Wheat', label: 'Wheat' },
  { value: 'Other', label: 'Other' },
]

interface PriceGuidance {
  grade_a_suggested_price: number
  grade_b_standard_price?: number
  grade_b_urgency_price?: number
  requires_cold_chain: boolean
  urgency_note?: string
  days_remaining?: number
}

interface CreatedOrder {
  id: string
  quality_grade?: string
  price_guidance?: PriceGuidance
}

const RECOMMENDED_BUYERS: Record<string, string[]> = {
  A: ['High-end Restaurants', 'Boutique Grocers', 'International Exporters'],
  PREMIUM: ['High-end Restaurants', 'Boutique Grocers', 'International Exporters'],
  B: ['Wholesale Markets', 'Local Grocers', 'Street Vendors'],
  P: ['Juiceries', 'Sauce Manufacturers', 'Livestock Feed'],
  PROCESSING: ['Juiceries', 'Sauce Manufacturers', 'Livestock Feed'],
}

export default function HarvestListing() {
  const navigate = useNavigate()
  const fileRef = useRef<HTMLInputElement>(null)

  const [cropType, setCropType] = useState('Tomato')
  const [variety, setVariety] = useState('')
  const [volume, setVolume] = useState('')
  const [harvestDate, setHarvestDate] = useState('')
  const [askingPrice, setAskingPrice] = useState('')
  const [coldChain, setColdChain] = useState(false)
  const [notes, setNotes] = useState('')
  const [_photos, setPhotos] = useState<File[]>([])
  const [previewUrls, setPreviewUrls] = useState<string[]>([])
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  // Grade modal state
  const [gradingResult, setGradingResult] = useState<CreatedOrder | null>(null)

  const handlePhotoChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files ?? []).slice(0, 5)
    setPhotos(files)
    setPreviewUrls(files.map((f) => URL.createObjectURL(f)))
  }

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const res = await createOrder({
        crop_type: cropType,
        variety: variety || undefined,
        total_volume_kg: parseFloat(volume),
        unit_price_asking: askingPrice ? parseFloat(askingPrice) : 0.5,
        requires_cold_chain: coldChain,
        harvest_date: harvestDate ? new Date(harvestDate).toISOString() : undefined,
      })
      setGradingResult(res.data)
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } }
      setError(e.response?.data?.detail ?? 'Failed to create listing')
    } finally {
      setLoading(false)
    }
  }

  // Grade result modal
  if (gradingResult) {
    const grade = gradingResult.quality_grade ?? 'B'
    const pg = gradingResult.price_guidance
    const buyers = RECOMMENDED_BUYERS[grade] ?? RECOMMENDED_BUYERS['B']
    return (
      <div className="min-h-screen bg-[#F5F2ED] flex items-center justify-center px-4">
        <div className="bg-white rounded-2xl shadow-lg p-6 max-w-sm w-full">
          <div className="flex items-center gap-3 mb-4">
            <span className={`rounded-full px-3 py-1 text-sm font-bold uppercase ${
              grade === 'A' || grade === 'PREMIUM' ? 'bg-green-100 text-green-800' :
              grade === 'B' ? 'bg-amber-100 text-amber-800' : 'bg-gray-100 text-gray-700'
            }`}>{grade}</span>
            <div>
              <p className={`font-bold text-xl ${
                grade === 'A' || grade === 'PREMIUM' ? 'text-green-700' : 'text-amber-700'
              }`}>GRADE {grade}</p>
            </div>
          </div>

          {pg && (
            <div className="mb-4">
              <p className="text-sm text-gray-600 mb-1">
                Suggested price: <strong>₹{pg.grade_a_suggested_price}/kg</strong>
              </p>
              {pg.grade_b_standard_price && (
                <p className="text-sm text-gray-600 mb-1">
                  Grade B standard: <strong>₹{pg.grade_b_standard_price}/kg</strong>
                </p>
              )}
              {pg.grade_b_urgency_price && (
                <p className="text-sm text-amber-600 mb-1">
                  Urgency price: <strong>₹{pg.grade_b_urgency_price}/kg</strong>
                </p>
              )}
              {pg.days_remaining !== undefined && (
                <p className="text-sm text-gray-500">Estimated shelf life: {pg.days_remaining} days</p>
              )}
              {pg.urgency_note && (
                <p className="text-xs text-amber-600 mt-2">{pg.urgency_note}</p>
              )}
            </div>
          )}

          {previewUrls.length > 0 && (
            <div className="flex gap-2 mb-4 overflow-x-auto">
              {previewUrls.map((url, i) => (
                <img key={i} src={url} alt="crop" className="w-20 h-20 object-cover rounded-xl flex-shrink-0" />
              ))}
            </div>
          )}

          <div className="mb-4">
            <p className="text-sm font-semibold text-gray-700 mb-1">Recommended Buyers</p>
            <div className="flex flex-wrap gap-1">
              {buyers.map((b) => (
                <span key={b} className="bg-gray-50 border border-gray-200 rounded-full px-3 py-1 text-xs text-gray-600">✓ {b}</span>
              ))}
            </div>
          </div>

          <div className="flex gap-3">
            <Button fullWidth onClick={() => navigate('/farmer/dashboard')}>
              Confirm Listing
            </Button>
            <Button variant="secondary" fullWidth onClick={() => setGradingResult(null)}>
              Retake Photo
            </Button>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-[#F5F2ED]">
      <div className="bg-white px-4 py-4 shadow-sm flex items-center gap-3">
        <button onClick={() => navigate(-1)} className="text-[#4A6741] text-sm font-medium">← Back</button>
        <h1 className="text-xl font-bold text-gray-800">New Listing</h1>
      </div>

      <div className="px-4 py-4">
        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <SelectField label="Crop Type" id="crop" options={CROP_OPTIONS}
            value={cropType} onChange={(e) => setCropType(e.target.value)} />
          <InputField label="Variety (optional)" id="variety" value={variety}
            onChange={(e) => setVariety(e.target.value)} placeholder="e.g. Roma, Totapuri" />
          <InputField label="Volume (kg)" id="volume" type="number" min="1"
            value={volume} onChange={(e) => setVolume(e.target.value)} required />
          <InputField label="Harvest Date" id="harvestDate" type="date"
            value={harvestDate} onChange={(e) => setHarvestDate(e.target.value)} />
          <InputField label="Asking Price per kg (₹) — leave blank for open bids" id="price"
            type="number" step="0.01" min="0"
            value={askingPrice} onChange={(e) => setAskingPrice(e.target.value)} />

          {/* Cold chain toggle */}
          <div className="flex items-center justify-between bg-white rounded-xl border border-gray-200 px-4 py-3">
            <span className="text-sm font-medium text-gray-700">Needs Cold Chain (Refrigerated)</span>
            <button type="button" onClick={() => setColdChain(!coldChain)}
              className={`w-12 h-6 rounded-full transition-colors ${coldChain ? 'bg-[#4A6741]' : 'bg-gray-200'}`}
            >
              <span className={`block w-5 h-5 bg-white rounded-full shadow transition-transform mx-0.5 ${coldChain ? 'translate-x-6' : 'translate-x-0'}`} />
            </button>
          </div>

          {/* Photo upload */}
          <div>
            <p className="text-sm font-medium text-gray-700 mb-2">Photos (up to 5)</p>
            <div
              className="border-2 border-dashed border-gray-200 rounded-xl p-6 text-center cursor-pointer hover:border-[#4A6741] transition-colors"
              onClick={() => fileRef.current?.click()}
            >
              <p className="text-4xl mb-2">📷</p>
              <p className="text-sm text-gray-500">Click to upload or take photos</p>
              <p className="text-xs text-gray-400 mt-1">Triggers AI grading</p>
              <input ref={fileRef} type="file" accept="image/*" multiple className="hidden"
                onChange={handlePhotoChange} />
            </div>
            {previewUrls.length > 0 && (
              <div className="flex gap-2 mt-3 overflow-x-auto">
                {previewUrls.map((url, i) => (
                  <img key={i} src={url} alt="preview" className="w-16 h-16 object-cover rounded-xl flex-shrink-0" />
                ))}
              </div>
            )}
          </div>

          <div className="flex flex-col gap-1">
            <label htmlFor="notes" className="text-sm font-medium text-gray-700">Notes (optional)</label>
            <textarea id="notes" rows={3}
              className="rounded-xl border border-gray-200 bg-white px-4 py-3 text-sm focus:border-[#4A6741] focus:outline-none"
              placeholder="Special handling, refrigeration needs, etc."
              value={notes} onChange={(e) => setNotes(e.target.value)}
            />
          </div>

          {error && <p className="text-red-600 text-sm">{error}</p>}

          <Button type="submit" fullWidth disabled={loading}>
            {loading ? 'Creating Listing…' : 'Create Listing'}
          </Button>
        </form>
      </div>
    </div>
  )
}
