import type { ButtonHTMLAttributes } from 'react'

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'danger'
  fullWidth?: boolean
}

export function Button({ variant = 'primary', fullWidth, className = '', children, ...rest }: Props) {
  const base = 'rounded-2xl px-6 py-3 font-semibold text-sm transition-colors focus:outline-none'
  const variants = {
    primary: 'bg-[#4A6741] text-white hover:bg-[#3a5232] disabled:opacity-50',
    secondary: 'bg-white text-[#4A6741] border border-[#4A6741] hover:bg-[#f0ede8]',
    danger: 'bg-red-600 text-white hover:bg-red-700',
  }
  return (
    <button
      className={`${base} ${variants[variant]} ${fullWidth ? 'w-full' : ''} ${className}`}
      {...rest}
    >
      {children}
    </button>
  )
}
