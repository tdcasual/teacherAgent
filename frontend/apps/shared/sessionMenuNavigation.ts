export type MenuMoveDirection = 'next' | 'prev' | 'first' | 'last'

export const getNextMenuIndex = (currentIndex: number, itemCount: number, direction: MenuMoveDirection): number => {
  if (!Number.isFinite(itemCount) || itemCount <= 0) return -1

  const count = Math.floor(itemCount)
  const validCurrent = Number.isFinite(currentIndex) && currentIndex >= 0 && currentIndex < count ? Math.floor(currentIndex) : -1

  if (direction === 'first') return 0
  if (direction === 'last') return count - 1
  if (direction === 'next') return validCurrent < 0 ? 0 : (validCurrent + 1) % count
  return validCurrent < 0 ? count - 1 : (validCurrent - 1 + count) % count
}
