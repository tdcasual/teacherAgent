import { useEffect, useRef, useState } from 'react'

type Props = {
  value: string
  onChange: (value: string) => void
  models: string[]
  loading?: boolean
  error?: string
  placeholder?: string
  onFocus?: () => void
}

export default function ModelCombobox({
  value,
  onChange,
  models,
  loading,
  error,
  placeholder,
  onFocus,
}: Props) {
  const [open, setOpen] = useState(false)
  const [filter, setFilter] = useState('')
  const [hasTyped, setHasTyped] = useState(false)
  const wrapRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const openRef = useRef(open)
  const filterRef = useRef(filter)
  const valueRef = useRef(value)
  const hasTypedRef = useRef(hasTyped)
  openRef.current = open
  filterRef.current = filter
  valueRef.current = value
  hasTypedRef.current = hasTyped

  const [highlightIndex, setHighlightIndex] = useState(-1)

  const activeFilter = hasTyped ? filter : ''
  const filtered = models.filter((model) => model.toLowerCase().includes(activeFilter.toLowerCase()))

  const modelCountLabel = !loading && models.length > 0 ? `共 ${models.length} 个模型` : ''

  const closeDropdown = () => {
    openRef.current = false
    filterRef.current = ''
    hasTypedRef.current = false
    setOpen(false)
    setFilter('')
    setHasTyped(false)
    setHighlightIndex(-1)
  }

  const openDropdown = () => {
    openRef.current = true
    filterRef.current = value
    hasTypedRef.current = false
    setOpen(true)
    setFilter(value)
    setHasTyped(false)
    setHighlightIndex(-1)
    onFocus?.()
  }

  const commitTypedIfNeeded = () => {
    if (openRef.current && hasTypedRef.current && filterRef.current !== valueRef.current) {
      onChange(filterRef.current)
    }
  }

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) {
        if (openRef.current && hasTypedRef.current && filterRef.current !== valueRef.current) {
          onChange(filterRef.current)
        }
        openRef.current = false
        filterRef.current = ''
        hasTypedRef.current = false
        setOpen(false)
        setFilter('')
        setHasTyped(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [onChange])

  const handleSelect = (model: string) => {
    onChange(model)
    closeDropdown()
  }

  return (
    <div className="relative" ref={wrapRef}>
      <div className="flex items-stretch">
        <input
          ref={inputRef}
          className="model-combobox-input flex-1 !rounded-tr-none !rounded-br-none min-w-0"
          value={open ? filter : value}
          onChange={(e) => {
            if (!open) {
              onChange(e.target.value)
            } else {
              filterRef.current = e.target.value
              hasTypedRef.current = true
              setFilter(e.target.value)
              setHasTyped(true)
            }
          }}
          onFocus={() => {
            if (!openRef.current) openDropdown()
          }}
          onKeyDown={(e) => {
            if (!open) return
            if (e.key === 'ArrowDown') {
              e.preventDefault()
              setHighlightIndex((prev) => (prev + 1 < filtered.length ? prev + 1 : 0))
            } else if (e.key === 'ArrowUp') {
              e.preventDefault()
              setHighlightIndex((prev) => (prev - 1 >= 0 ? prev - 1 : filtered.length - 1))
            } else if (e.key === 'Enter') {
              e.preventDefault()
              if (highlightIndex >= 0 && highlightIndex < filtered.length) {
                handleSelect(filtered[highlightIndex])
              } else {
                commitTypedIfNeeded()
                closeDropdown()
              }
            } else if (e.key === 'Escape') {
              e.preventDefault()
              closeDropdown()
            }
          }}
          placeholder={loading ? '正在拉取模型列表…' : placeholder || '选择或输入模型 ID'}
        />
        <button
          type="button"
          className="border border-border border-l-0 bg-surface-soft px-[10px] cursor-pointer text-[12px] text-muted rounded-r-[12px] flex-shrink-0 transition-colors duration-150 hover:bg-surface-hover"
          tabIndex={-1}
          onMouseDown={(e) => {
            e.preventDefault()
            if (openRef.current) {
              commitTypedIfNeeded()
              closeDropdown()
            } else {
              openDropdown()
              inputRef.current?.focus()
            }
          }}
          aria-label="展开模型列表"
        >
          ▾
        </button>
      </div>
      {open && (
        <div className="absolute top-full left-0 right-0 z-10 mt-[2px] max-h-[min(340px,52vh)] overflow-y-auto bg-white border border-border rounded-[12px] shadow-md flex flex-col">
          {modelCountLabel ? <div className="sticky top-0 z-[1] px-[10px] py-[6px] text-[12px] text-muted bg-[#f8fafb] border-b border-border">{modelCountLabel}</div> : null}
          {loading && <div className="px-[10px] py-[7px] text-[12px] text-muted">加载中…</div>}
          {error && <div className="px-[10px] py-[7px] text-[12px] text-danger">{error}</div>}
          {!loading && filtered.length === 0 && (
            <div className="px-[10px] py-[7px] text-[12px] text-muted">无匹配模型，可直接输入</div>
          )}
          {filtered.map((model, idx) => (
            <button
              key={model}
              type="button"
              className={`model-combobox-option border-none bg-transparent text-left px-[10px] py-[8px] text-[13px] cursor-pointer text-ink leading-[1.35] whitespace-normal break-all hover:bg-surface-soft ${model === value ? 'bg-accent-soft text-accent font-semibold' : ''} ${idx === highlightIndex ? 'bg-surface-soft' : ''}`}
              title={model}
              onMouseDown={(e) => {
                e.preventDefault()
                handleSelect(model)
              }}
            >
              {model}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
