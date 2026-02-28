import { useState } from 'react'
import type { FormEvent } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { InputField } from './InputField'
import { Button } from './Button'

interface Props {
  title: string
  role: 'farmer' | 'buyer' | 'trucker'
  loginFn: (email: string, password: string) => Promise<{ data: { access_token: string; role: string; user_id?: string } }>
  afterLoginPath: string
  backPath: string
  demoEmail: string
  demoPassword?: string
}

export function LoginForm({ title, role, loginFn, afterLoginPath, backPath, demoEmail, demoPassword = 'demo1234' }: Props) {
  const { login } = useAuth()
  const navigate = useNavigate()
  const [email, setEmail] = useState(demoEmail)
  const [password, setPassword] = useState(demoPassword)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const res = await loginFn(email, password)
      const { access_token } = res.data
      // Decode JWT payload (base64url) to extract the user's UUID from the 'sub' claim
      const payload = JSON.parse(atob(access_token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/')))
      login(access_token, role, payload.sub ?? '')
      navigate(afterLoginPath)
    } catch {
      setError('Invalid email or password')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-[#F5F2ED] flex flex-col items-center justify-center px-4">
      <div className="w-full max-w-sm bg-white rounded-2xl shadow-sm p-8">
        <Link to={backPath} className="text-sm text-[#4A6741] mb-6 inline-block">← Back</Link>
        <h2 className="text-2xl font-bold text-gray-800 mb-6">{title}</h2>
        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <InputField label="Email" id="email" type="email" value={email}
            onChange={(e) => setEmail(e.target.value)} required />
          <InputField label="Password" id="password" type="password" value={password}
            onChange={(e) => setPassword(e.target.value)} required />
          {error && <p className="text-red-600 text-sm">{error}</p>}
          <Button type="submit" fullWidth disabled={loading}>
            {loading ? 'Signing in…' : 'Sign In'}
          </Button>
        </form>
        <p className="text-xs text-gray-400 mt-4 text-center">
          Demo: {demoEmail} / {demoPassword}
        </p>
      </div>
    </div>
  )
}
