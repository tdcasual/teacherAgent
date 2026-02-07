import { useCallback, useEffect, useRef, useState } from 'react'

type UseChatScrollArgs = {
  activeSessionId: string
  messages: unknown[]
  sending: boolean
}

export const useChatScroll = ({ activeSessionId, messages, sending }: UseChatScrollArgs) => {
  const [showScrollToBottom, setShowScrollToBottom] = useState(false)
  const messagesRef = useRef<HTMLDivElement | null>(null)
  const shouldAutoScrollRef = useRef(true)

  const enableAutoScroll = useCallback(() => {
    shouldAutoScrollRef.current = true
    setShowScrollToBottom(false)
  }, [])

  const scrollMessagesToBottom = useCallback((behavior: ScrollBehavior = 'smooth') => {
    const el = messagesRef.current
    if (!el) return
    el.scrollTo({ top: el.scrollHeight, behavior })
    shouldAutoScrollRef.current = true
    setShowScrollToBottom(false)
  }, [])

  const handleMessagesScroll = useCallback(() => {
    const el = messagesRef.current
    if (!el) return
    const distance = el.scrollHeight - el.scrollTop - el.clientHeight
    const nearBottom = distance <= 64
    shouldAutoScrollRef.current = nearBottom
    setShowScrollToBottom(!nearBottom)
  }, [])

  useEffect(() => {
    enableAutoScroll()
  }, [activeSessionId, enableAutoScroll])

  useEffect(() => {
    if (!shouldAutoScrollRef.current) return
    requestAnimationFrame(() => {
      scrollMessagesToBottom('auto')
    })
  }, [messages, sending, scrollMessagesToBottom])

  return {
    messagesRef,
    showScrollToBottom,
    enableAutoScroll,
    handleMessagesScroll,
    scrollMessagesToBottom,
  }
}
