import React, { useRef, useState, useLayoutEffect } from 'react'

const MIN_HEIGHT_PX = 96
const MAX_HEIGHT_PX = 360

const ChatBox = ({ onSubmit, loading = false }) => {
  const textareaRef = useRef(null)
  const [value, setValue] = useState('')

  useLayoutEffect(() => {
    const el = textareaRef.current
    if (!el) return
    el.style.height = 'auto'
    const next = Math.min(Math.max(el.scrollHeight, MIN_HEIGHT_PX), MAX_HEIGHT_PX)
    el.style.height = `${next}px`
    el.style.overflowY = el.scrollHeight > MAX_HEIGHT_PX ? 'auto' : 'hidden'
  }, [value])

  const canSubmit = value.trim().length > 0 && !loading

  const handleSubmit = () => {
    if (!canSubmit) return
    onSubmit?.(value.trim())
  }

  const handleKeyDown = (e) => {
    if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
      e.preventDefault()
      handleSubmit()
    }
  }

  return (
    <div className='w-full max-w-[760px] rounded-card border border-line bg-surface px-4 pt-4 pb-4 sm:px-5 sm:pt-5 shadow-[0_1px_2px_rgba(17,20,24,0.04)] transition-shadow focus-within:shadow-[0_4px_20px_rgba(17,20,24,0.08)]'>
      <div className='rounded-field bg-canvas px-4 py-3.5 transition-colors focus-within:ring-2 focus-within:ring-brand/20'>
        <textarea
          ref={textareaRef}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
          rows={1}
          placeholder='Paste your source material here…'
          aria-label='Source material'
          className='w-full resize-none bg-transparent text-[15px] leading-[1.45] text-ink placeholder:text-subtle outline-none'
        />
      </div>

      <div className='mt-4 flex flex-col-reverse gap-3 sm:flex-row sm:items-center sm:gap-3'>
        <p className='text-[12px] leading-[1.45] text-subtle text-center sm:text-left'>
          {value.length.toLocaleString()} characters &nbsp;·&nbsp; longer sources make better briefs
        </p>

        <div className='hidden sm:block sm:flex-1' />

        <button
          type='button'
          onClick={handleSubmit}
          disabled={!canSubmit}
          className='w-full sm:w-auto inline-flex items-center justify-center gap-2 rounded-field bg-brand px-5 py-3 text-[14px] font-semibold text-white transition-colors hover:bg-brand-strong focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand disabled:opacity-40 disabled:cursor-not-allowed'
        >
          {loading && <i className='pi pi-spin pi-spinner text-[13px]' />}
          {loading ? 'Generating…' : 'Generate posts'}
        </button>
      </div>
    </div>
  )
}

export default ChatBox
