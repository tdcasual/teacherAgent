import { useEffect, type RefObject } from 'react'

type DismissibleLayerOptions = {
  open: boolean
  onDismiss: () => void
  refs: ReadonlyArray<RefObject<HTMLElement | null>>
  closeOnEscape?: boolean
  closeOnPointerDownOutside?: boolean
}

export const useDismissibleLayer = ({
  open,
  onDismiss,
  refs,
  closeOnEscape = true,
  closeOnPointerDownOutside = true,
}: DismissibleLayerOptions) => {
  useEffect(() => {
    if (!open) return

    const isTargetInsideAnyRef = (target: Node | null) =>
      refs.some((ref) => {
        const element = ref.current
        return Boolean(element && target && element.contains(target))
      })

    const handlePointerDown = (event: PointerEvent) => {
      if (!closeOnPointerDownOutside) return
      const target = event.target as Node | null
      if (isTargetInsideAnyRef(target)) return
      onDismiss()
    }

    const handleKeyDown = (event: KeyboardEvent) => {
      if (!closeOnEscape || event.key !== 'Escape') return
      onDismiss()
    }

    if (closeOnPointerDownOutside) {
      document.addEventListener('pointerdown', handlePointerDown)
    }
    if (closeOnEscape) {
      document.addEventListener('keydown', handleKeyDown)
    }

    return () => {
      if (closeOnPointerDownOutside) {
        document.removeEventListener('pointerdown', handlePointerDown)
      }
      if (closeOnEscape) {
        document.removeEventListener('keydown', handleKeyDown)
      }
    }
  }, [open, onDismiss, refs, closeOnEscape, closeOnPointerDownOutside])
}
