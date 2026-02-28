import { useNavigate } from 'react-router-dom'

const roles = [
  {
    key: 'farmer',
    emoji: '🌾',
    title: 'Farmer',
    subtitle: 'Post a harvest listing',
    path: '/farmer/login',
  },
  {
    key: 'buyer',
    emoji: '🏭',
    title: 'Buyer',
    subtitle: 'Browse & bid on lots',
    path: '/buyer/login',
  },
  {
    key: 'trucker',
    emoji: '🚛',
    title: 'Trucker',
    subtitle: 'Accept backhaul jobs',
    path: '/trucker/login',
  },
]

export default function RoleSelection() {
  const navigate = useNavigate()

  return (
    <div className="min-h-screen bg-[#F5F2ED] flex flex-col items-center justify-center px-4 py-12">
      <div className="w-full max-w-sm">
        <h1 className="text-3xl font-bold text-center text-[#4A6741] mb-1">AgriMatch</h1>
        <p className="text-center text-gray-500 mb-8">Select your user role:</p>

        <div className="flex flex-col gap-4">
          {roles.map((role) => (
            <div
              key={role.key}
              className="bg-white rounded-2xl shadow-sm p-5 flex flex-col gap-3 cursor-pointer border border-transparent hover:border-[#4A6741] transition-all"
              onClick={() => navigate(role.path)}
            >
              <div className="flex items-center gap-3">
                <span className="text-4xl">{role.emoji}</span>
                <div>
                  <div className="font-bold text-lg text-gray-800">{role.title}</div>
                  <div className="text-sm text-gray-500">{role.subtitle}</div>
                </div>
              </div>
              <button
                className="w-full bg-[#4A6741] text-white rounded-xl py-3 font-semibold hover:bg-[#3a5232] transition-colors"
                onClick={(e) => { e.stopPropagation(); navigate(role.path) }}
              >
                Continue
              </button>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
