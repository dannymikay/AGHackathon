import { useEffect, useRef, useState } from 'react'

export interface WsMessage {
  type: string
  [key: string]: unknown
}

export function useWebSocket(orderId: string | null, token: string | null) {
  const [lastMessage, setLastMessage] = useState<WsMessage | null>(null)
  const [orderStatus, setOrderStatus] = useState<string | null>(null)
  const [escrowStatus, setEscrowStatus] = useState<string | null>(null)
  const wsRef = useRef<WebSocket | null>(null)

  useEffect(() => {
    if (!orderId || !token) return

    const url = `ws://localhost:8000/ws/orders/${orderId}?token=${token}`
    const ws = new WebSocket(url)
    wsRef.current = ws

    ws.onmessage = (event) => {
      try {
        const msg: WsMessage = JSON.parse(event.data)
        setLastMessage(msg)
        if (msg.type === 'STATE_SYNC' || msg.type === 'FSM_TRANSITION') {
          if (msg.order_status) setOrderStatus(msg.order_status as string)
          if (msg.escrow_status) setEscrowStatus(msg.escrow_status as string)
        }
        if (msg.type === 'PING') ws.send(JSON.stringify({ type: 'PONG' }))
      } catch {}
    }

    return () => ws.close()
  }, [orderId, token])

  return { lastMessage, orderStatus, escrowStatus }
}
