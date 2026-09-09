import React, { useState, useRef, useEffect } from 'react'

export const shortId = (id) => (id ? id.replace(/-/g, '').slice(0, 6) : '')

const relativeTime = (ts) => {
  if (!ts) return ''
  const mins = Math.floor((Date.now() - ts) / 60000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  return `${Math.floor(hrs / 24)}d ago`
}

const ThreadDropdown = ({ threads = [], activeId, onSelect, onRemove }) => {
  const [open, setOpen] = useState(false)
  const [copiedId, setCopiedId] = useState(null)
  const boxRef = useRef(null)

  useEffect(() => {
    if (!open) return
    const onDocClick = (e) => {
      if (boxRef.current && !boxRef.current.contains(e.target)) setOpen(false)
    }
    const onEsc = (e) => e.key === 'Escape' && setOpen(false)

    document.addEventListener('mousedown', onDocClick)
    document.addEventListener('keydown', onEsc)
    return () => {
      document.removeEventListener('mousedown', onDocClick)
      document.removeEventListener('keydown', onEsc)
    }
  }, [open])

  if (threads.length === 0) return null

  const active = threads.find((t) => t.id === activeId)

  const copyId = async (e, id) => {
    e.stopPropagation()
    try {
      await navigator.clipboard.writeText(id)
      setCopiedId(id)
      setTimeout(() => setCopiedId(null), 1400)
    } catch {
      setCopiedId(null)
    }
  }

  return (
    <div ref={boxRef} className='relative'>
      <button
        type='button'
        onClick={() => setOpen(!open)}
        aria-haspopup='listbox'
        aria-expanded={open}
        className='flex items-center gap-2 rounded-full bg-canvas px-3 py-1.5 text-[12.5px] text-muted transition-colors hover:bg-line/60'
      >
        <i className='pi pi-comments text-[11px]' />
        <span className='max-w-[120px] truncate'>
          {active ? `Thread ${shortId(active.id)}` : 'Select thread'}
        </span>
        <span className='rounded-full bg-brand/10 px-1.5 text-[11px] font-medium text-brand'>
          {threads.length}
        </span>
        <i
          className={`pi pi-chevron-down text-[10px] transition-transform ${open ? 'rotate-180' : ''}`}
        />
      </button>

      {open && (
        <div
          role='listbox'
          className='absolute right-0 z-30 mt-2 w-[300px] overflow-hidden rounded-card border border-line bg-surface shadow-[0_8px_28px_rgba(17,20,24,0.12)]'
        >
          <p className='border-b border-line px-3 py-2 text-[11px] font-medium uppercase tracking-wide text-subtle'>
            {threads.length} thread{threads.length > 1 ? 's' : ''}
          </p>

          <ul className='max-h-[340px] overflow-y-auto'>
            {threads.map((thread) => {
              const isActive = thread.id === activeId
              return (
                <li
                  key={thread.id}
                  role='option'
                  aria-selected={isActive}
                  className={`group flex items-start gap-2 px-3 py-2.5 transition-colors hover:bg-canvas ${
                    isActive ? 'bg-canvas' : ''
                  }`}
                >
                  <i
                    className={`pi pi-check mt-1 text-[11px] ${isActive ? 'text-brand' : 'invisible'}`}
                  />

                  <button
                    type='button'
                    onClick={() => {
                      onSelect(thread.id)
                      setOpen(false)
                    }}
                    className='min-w-0 flex-1 text-left'
                  >
                    <span className='block truncate text-[13px] text-ink'>{thread.title}</span>
                    <span className='mt-0.5 block font-mono text-[11px] text-subtle'>
                      {shortId(thread.id)} · {relativeTime(thread.updatedAt || thread.createdAt)}
                    </span>
                  </button>

                  <span className='flex shrink-0 items-center gap-0.5 opacity-0 transition-opacity group-hover:opacity-100 focus-within:opacity-100'>
                    <button
                      type='button'
                      onClick={(e) => copyId(e, thread.id)}
                      title='Copy full thread id'
                      className='rounded p-1.5 text-subtle transition-colors hover:bg-line/60 hover:text-ink'
                    >
                      <i className={`pi ${copiedId === thread.id ? 'pi-check' : 'pi-copy'} text-[11px]`} />
                    </button>

                    <button
                      type='button'
                      onClick={(e) => {
                        e.stopPropagation()
                        onRemove?.(thread.id)
                      }}
                      title='Remove from list'
                      className='rounded p-1.5 text-subtle transition-colors hover:bg-red-50 hover:text-red-600'
                    >
                      <i className='pi pi-trash text-[11px]' />
                    </button>
                  </span>
                </li>
              )
            })}
          </ul>

          <p className='border-t border-line px-3 py-2 text-[11px] leading-[1.4] text-subtle'>
            Follow-ups apply to the selected thread.
          </p>
        </div>
      )}
    </div>
  )
}

export default ThreadDropdown
