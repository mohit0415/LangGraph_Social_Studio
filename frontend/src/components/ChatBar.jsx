import React, { useState, useRef, useLayoutEffect } from 'react'

const MIN_HEIGHT_PX = 24
const MAX_HEIGHT_PX = 160

const ChatBar = ({ onSend, busy, clarify, onDismissClarify }) => {
  const [value, setValue] = useState('')
  const ref = useRef(null)

  const pickTarget = (opt) => {
    setValue((v) => (v.trim() ? `${opt}: ${v.trim()}` : `${opt}: `))
    ref.current?.focus()
  }

  useLayoutEffect(() => {
    const el = ref.current
    if (!el) return
    el.style.height = 'auto'
    const next = Math.min(Math.max(el.scrollHeight, MIN_HEIGHT_PX), MAX_HEIGHT_PX)
    el.style.height = `${next}px`
    el.style.overflowY = el.scrollHeight > MAX_HEIGHT_PX ? 'auto' : 'hidden'
  }, [value])

  const submit = () => {
    const text = value.trim()
    if (!text || busy) return
    onSend(text)
    setValue('')
  }

  const onKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      submit()
    }
  }

  return (
    <div className='space-y-3'>
      {clarify && (
        <div className='rounded-card border border-amber-200 bg-amber-50 p-4'>
          <div className='flex items-start gap-3'>
            <p className='flex-1 text-[13.5px] text-amber-900'>{clarify.message}</p>
            <button
              type='button'
              onClick={onDismissClarify}
              aria-label='Dismiss'
              className='shrink-0 rounded p-1 text-amber-700 transition-colors hover:bg-amber-100'
            >
              <i className='pi pi-times text-[11px]' />
            </button>
          </div>

          {clarify.options?.length > 0 && (
            <div className='mt-2.5 flex flex-wrap gap-2'>
              {clarify.options.map((opt) => (
                <button
                  key={opt}
                  type='button'
                  onClick={() => pickTarget(opt)}
                  className='rounded-full border border-amber-300 bg-white px-2.5 py-1 text-[12px] text-amber-900 transition-colors hover:bg-amber-100'
                >
                  {opt}
                </button>
              ))}
            </div>
          )}

          <p className='mt-2.5 text-[11.5px] text-amber-700'>
            Pick a target, then say what to change — the router needs both.
          </p>
        </div>
      )}

      <div className='flex items-end gap-3 rounded-card border border-line bg-surface px-4 py-3 transition-colors focus-within:border-brand'>
        <textarea
          ref={ref}
          rows={1}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={onKeyDown}
          disabled={busy}
          placeholder='Ask for a change — "make the Instagram one warmer", "review and refine all posts"…'
          aria-label='Follow-up instruction'
          className='w-full resize-none bg-transparent py-1.5 text-[14px] leading-[1.5] text-ink placeholder:text-subtle outline-none disabled:opacity-50'
        />

        <button
          type='button'
          onClick={submit}
          disabled={busy || !value.trim()}
          className='shrink-0 rounded-field bg-brand px-4 py-2.5 text-[13.5px] font-semibold text-white transition-colors hover:bg-brand-strong disabled:opacity-40 disabled:cursor-not-allowed'
        >
          {busy ? <i className='pi pi-spin pi-spinner text-[13px]' /> : 'Send'}
        </button>
      </div>
    </div>
  )
}

export default ChatBar
