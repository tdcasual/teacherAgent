import { useCallback, useEffect, useRef, useState } from 'react'

const NEAR_BOTTOM_THRESHOLD = 80
const CACHE_MAX = 500

/**
 * Smart auto-scroll hook: only scrolls to bottom when user is already near
 * the bottom. Exposes isNearBottom state and manual scrollToBottom().
 */
export function useSmartAutoScroll() {
  const messagesRef = useRef<HTMLDivElement>(null)
  const endRef = useRef<HTMLDivElement>(null)
  const [isNearBottom, setIsNearBottom] = useState(true)

  useEffect(() => {
    const el = messagesRef.current
    if (!el) return

    const onScroll = () => {
      const gap = el.scrollHeight - el.scrollTop - el.clientHeight
      setIsNearBottom(gap < NEAR_BOTTOM_THRESHOLD)
    }

    el.addEventListener('scroll', onScroll, { passive: true })
    return () => el.removeEventListener('scroll', onScroll)
  }, [])

  const scrollToBottom = useCallback(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [])

  const autoScroll = useCallback(() => {
    if (isNearBottom) {
      endRef.current?.scrollIntoView({ behavior: 'smooth' })
    }
  }, [isNearBottom])

  return { messagesRef, endRef, isNearBottom, scrollToBottom, autoScroll }
}

/**
 * Preserve scroll position when prepending older messages.
 * Call saveScrollHeight() before inserting, restoreScrollPosition() after.
 */
export function useScrollPositionLock(containerRef: React.RefObject<HTMLDivElement | null>) {
  const savedHeight = useRef(0)

  const saveScrollHeight = useCallback(() => {
    if (containerRef.current) {
      savedHeight.current = containerRef.current.scrollHeight
    }
  }, [containerRef])

  const restoreScrollPosition = useCallback(() => {
    const el = containerRef.current
    if (el) {
      el.scrollTop += el.scrollHeight - savedHeight.current
    }
  }, [containerRef])

  return { saveScrollHeight, restoreScrollPosition }
}

/**
 * Simple LRU-like eviction for a Map cache.
 * Map preserves insertion order, so we delete the oldest entries.
 */
export function evictOldestEntries<K, V>(cache: Map<K, V>, max: number = CACHE_MAX) {
  if (cache.size <= max) return
  const excess = cache.size - max
  const iter = cache.keys()
  for (let i = 0; i < excess; i++) {
    const { value, done } = iter.next()
    if (done) break
    cache.delete(value)
  }
}
