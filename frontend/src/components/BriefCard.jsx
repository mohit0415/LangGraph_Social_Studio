import React, { useState } from 'react'

const BriefCard = ({ brief }) => {
  const [open, setOpen] = useState(true)

  return (
    <section className='rounded-card border border-line bg-surface p-5'>
      <header className='flex items-center gap-3'>
        <h2 className='text-[15px] font-semibold text-ink'>Brief</h2>
        <span className='hidden sm:inline rounded-full bg-canvas px-2.5 py-1 text-[12px] text-muted'>
          written once · shared by all writers
        </span>
        <div className='flex-1' />
        <button
          type='button'
          onClick={() => setOpen(!open)}
          className='text-[13px] text-brand transition-colors hover:underline'
        >
          {open ? 'Hide' : 'Show'}
        </button>
      </header>

      {open && (
        <p className='mt-4 whitespace-pre-wrap text-[13.5px] leading-[1.6] text-muted'>
          {brief}
        </p>
      )}
    </section>
  )
}

export default BriefCard
