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
  }

  const openDropdown = () => {
    openRef.current = true
    filterRef.current = value
    hasTypedRef.current = false
    setOpen(true)
    setFilter(value)
    setHasTyped(false)
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
    <div className="model-combobox" ref={wrapRef}>
      <div className="model-combobox-input-wrap">
        <input
          ref={inputRef}
          className="model-combobox-input"
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
          placeholder={loading ? '正在拉取模型列表…' : placeholder || '选择或输入模型 ID'}
        />
        <button
          type="button"
          className="model-combobox-toggle"
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
        <div className="model-combobox-dropdown">
          {modelCountLabel ? <div className="model-combobox-count">{modelCountLabel}</div> : null}
          {loading && <div className="model-combobox-status">加载中…</div>}
          {error && <div className="model-combobox-status model-combobox-error">{error}</div>}
          {!loading && filtered.length === 0 && (
            <div className="model-combobox-status">无匹配模型，可直接输入</div>
          )}
          {filtered.map((model) => (
            <button
              key={model}
              type="button"
              className={`model-combobox-option ${model === value ? 'selected' : ''}`}
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
