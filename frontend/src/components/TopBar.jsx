import React from 'react'
import ThreadDropdown from './ThreadDropdown'

const TopBar = ({
  threads = [],
  activeId,
  onSelectThread,
  onNewSource,
  onRemoveThread,
  onSignOut,
}) => {
  const hasThreads = threads.length > 0

  return (
    <header className='sticky top-0 z-20 w-full border-b border-line bg-surface'>
      <div className='flex items-center gap-2 sm:gap-3 px-4 sm:px-8 py-3.5 sm:py-4'>
        <i className='pi pi-sparkles text-brand text-xl sm:text-2xl' />

        <span className='font-semibold text-ink text-[15px] sm:text-[16px] whitespace-nowrap'>
          Content Studio
        </span>

        <div className='flex-1' />

        {hasThreads ? (
          <ThreadDropdown
            threads={threads}
            activeId={activeId}
            onSelect={onSelectThread}
            onRemove={onRemoveThread}
          />
        ) : (
          <span className='text-subtle text-[13px] whitespace-nowrap'>No active thread</span>
        )}

        {hasThreads && (
          <button
            type='button'
            onClick={onNewSource}
            className='flex items-center gap-1.5 rounded-full bg-canvas px-3 py-1.5 text-[12.5px] text-muted transition-colors hover:bg-brand hover:text-white'
          >
            <i className='pi pi-plus text-[10px]' />
            <span className='hidden sm:inline'>New source</span>
          </button>
        )}

        <button
          type='button'
          onClick={onSignOut}
          title='Sign out'
          className='rounded-full p-2 text-subtle transition-colors hover:bg-canvas hover:text-red-600'
        >
          <i className='pi pi-sign-out text-[13px]' />
        </button>
      </div>
    </header>
  )
}

export default TopBar
