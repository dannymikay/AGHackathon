interface Props {
  grade: string
}

const gradeStyles: Record<string, string> = {
  A: 'bg-green-100 text-green-800',
  PREMIUM: 'bg-green-100 text-green-800',
  B: 'bg-amber-100 text-amber-800',
  P: 'bg-gray-100 text-gray-700',
  PROCESSING: 'bg-gray-100 text-gray-700',
}

export function GradeBadge({ grade }: Props) {
  const style = gradeStyles[grade] ?? 'bg-gray-100 text-gray-700'
  return (
    <span className={`inline-block rounded-full px-2 py-0.5 text-xs font-bold uppercase ${style}`}>
      {grade}
    </span>
  )
}

const STATUS_LABELS: Record<string, string> = {
  LISTED: 'Listed',
  NEGOTIATING: 'Has Bids',
  LOGISTICS_SEARCH: 'Finding Trucker',
  IN_TRANSIT: 'In Transit',
  SETTLED: 'Completed',
  CANCELLED: 'Cancelled',
}

export function StatusBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    LISTED: 'bg-blue-100 text-blue-700',
    NEGOTIATING: 'bg-yellow-100 text-yellow-700',
    LOGISTICS_SEARCH: 'bg-orange-100 text-orange-700',
    IN_TRANSIT: 'bg-purple-100 text-purple-700',
    SETTLED: 'bg-green-100 text-green-700',
    CANCELLED: 'bg-red-100 text-red-700',
  }
  const style = styles[status] ?? 'bg-gray-100 text-gray-600'
  const label = STATUS_LABELS[status] ?? status.replace(/_/g, ' ')
  return (
    <span className={`inline-block rounded-full px-3 py-1 text-xs font-semibold ${style}`}>
      {label}
    </span>
  )
}
