import { useCallback, useEffect, useRef, useState } from 'react'

const STORAGE_KEY = 'teacherWorkbenchWidth'
const DEFAULT_WIDTH = 320
const MIN_WIDTH = 200
const MAX_WIDTH = 600

export function useWorkbenchResize() {
  const [width, setWidth] = useState(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY)
      if (stored) {
        const n = Number(stored)
        if (Number.isFinite(n) && n >= MIN_WIDTH && n <= MAX_WIDTH) return n
      }
    } catch { /* ignore */ }
    return DEFAULT_WIDTH
  })
  const [isDragging, setIsDragging] = useState(false)
  const widthRef = useRef(width)

  useEffect(() => {
    document.documentElement.style.setProperty('--workbench-width', `${width}px`)
    widthRef.current = width
  }, [width])

  const onMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault()
    setIsDragging(true)
    const startX = e.clientX
    const startWidth = widthRef.current

    const onMouseMove = (ev: MouseEvent) => {
      const delta = startX - ev.clientX
      const next = Math.min(MAX_WIDTH, Math.max(MIN_WIDTH, startWidth + delta))
      setWidth(next)
    }

    const onMouseUp = () => {
      setIsDragging(false)
      document.removeEventListener('mousemove', onMouseMove)
      document.removeEventListener('mouseup', onMouseUp)
      document.body.style.userSelect = ''
      document.body.style.cursor = ''
      try {
        localStorage.setItem(STORAGE_KEY, String(widthRef.current))
      } catch { /* ignore */ }
    }

    document.body.style.userSelect = 'none'
    document.body.style.cursor = 'col-resize'
    document.addEventListener('mousemove', onMouseMove)
    document.addEventListener('mouseup', onMouseUp)
  }, [])

  return { width, isDragging, onResizeMouseDown: onMouseDown }
}
