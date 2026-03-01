import axios from 'axios'

// In development the Vite proxy rewrites /api → http://localhost:8000.
// In production set VITE_API_BASE_URL to your deployed backend URL, e.g.
//   https://agrimatch-backend.railway.app
// Strip any trailing slash from the env var to prevent double-slash paths
const _apiBase = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/+$/, '')
const api = axios.create({
  baseURL: _apiBase ? `${_apiBase}/api/v1` : '/api/v1',
})

// Inject auth token on every request
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// ── Auth ──────────────────────────────────────────────────────────────────────
export const farmerLogin = (email: string, password: string) =>
  api.post('/auth/farmer/login', { email, password })

export const buyerLogin = (email: string, password: string) =>
  api.post('/auth/buyer/login', { email, password })

export const truckerLogin = (email: string, password: string) =>
  api.post('/auth/middleman/login', { email, password })

// ── Orders ───────────────────────────────────────────────────────────────────
export const listOrders = (params?: Record<string, string>) =>
  api.get('/orders', { params })

export const getOrder = (id: string) => api.get(`/orders/${id}`)

export const createOrder = (data: {
  crop_type: string
  variety?: string
  total_volume_kg: number
  unit_price_asking: number
  requires_cold_chain?: boolean
  harvest_date?: string
  quality_grade?: string
}) => api.post('/orders', data)

export const getPriceGuidance = (cropType: string, askingPrice: number, harvestDate?: string) =>
  api.get(`/orders/price-guidance/${cropType}`, {
    params: { asking_price: askingPrice, ...(harvestDate ? { harvest_date: harvestDate } : {}) },
  })

// ── Bids ─────────────────────────────────────────────────────────────────────
export const submitBid = (data: {
  order_id: string
  offered_price_per_kg: number
  volume_kg: number
  message?: string
}) => api.post('/bids', data)

export const listBidsForOrder = (orderId: string) => api.get(`/bids/order/${orderId}`)

export const acceptBid = (bidId: string) => api.post(`/bids/${bidId}/accept`)

export const rejectBid = (bidId: string) => api.post(`/bids/${bidId}/reject`)

export const withdrawBid = (bidId: string) => api.delete(`/bids/${bidId}`)

// ── Logistics ─────────────────────────────────────────────────────────────────
export const searchNearbyTruckers = (orderId: string) =>
  api.get(`/logistics/search/${orderId}`)

export const acceptAssignment = (assignmentId: string) =>
  api.post(`/logistics/accept/${assignmentId}`)

// Accept a LOGISTICS_SEARCH order directly (creates assignment + transitions to IN_TRANSIT)
export const acceptOrderDirectly = (orderId: string) =>
  api.post(`/logistics/accept-order/${orderId}`)

export const rejectAssignment = (assignmentId: string) =>
  api.post(`/logistics/reject/${assignmentId}`)

// ── Verify ───────────────────────────────────────────────────────────────────
export const verifyPickup = (data: {
  order_id: string
  qr_token: string
  middleman_location: { latitude: number; longitude: number }
}) => api.post('/verify/pickup', data)

export const verifyDelivery = (data: {
  order_id: string
  qr_token: string
  middleman_location: { latitude: number; longitude: number }
}) => api.post('/verify/delivery', data)
