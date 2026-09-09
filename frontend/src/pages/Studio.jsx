import React from 'react'
import { useDispatch } from 'react-redux'
import { useNavigate } from 'react-router-dom'
import { AUTH_LOGOUT } from '../store/authReducer'
import { logoutStudio } from '../utils/studio_api'
import TopBar from '../components/TopBar'
import SourceInput from './SourceInput'
import Results from './Results'
import { BriefSkeleton, PostsRowSkeleton, TraceSkeleton } from '../components/Skeletons'
import { useStudio } from '../hooks/useStudio'

const Studio = () => {
  const dispatch = useDispatch()
  const navigate = useNavigate()

  const handleSignOut = async () => {
    // Ask the backend to drop the session first, so the Azure key it is holding
    // is discarded rather than left to idle out.
    await logoutStudio()
    dispatch({ type: AUTH_LOGOUT })
    navigate('/', { replace: true })
  }

  const {
    threads,
    activeThread,
    activeId,
    error,
    clarify,
    limits,
    isGenerating,
    isRefining,
    isLoadingThread,
    generate,
    followUp,
    selectThread,
    newSource,
    dismissClarify,
    removeThread,
  } = useStudio()

  const handleRefinePlatform = (platform) => {
    followUp(`Refine the ${platform} post — tighten the opening and cut filler.`)
  }

  return (
    <div className='min-h-screen bg-canvas font-sans'>
      <TopBar
        threads={threads}
        activeId={activeId}
        onSelectThread={selectThread}
        onNewSource={newSource}
        onRemoveThread={removeThread}
        onSignOut={handleSignOut}
      />

      {isGenerating || isLoadingThread ? (
        <div className='mx-auto grid max-w-[1440px] gap-6 px-4 py-6 sm:px-6 lg:grid-cols-[1fr_320px] xl:grid-cols-[1fr_340px]'>
          <div className='min-w-0 space-y-6'>
            <p className='flex items-center gap-2 text-[13.5px] text-muted'>
              <i className='pi pi-spin pi-spinner text-brand' />
              {isLoadingThread
                ? 'Loading this thread…'
                : 'Writing the brief, then all three posts in parallel…'}
            </p>
            <BriefSkeleton />
            <PostsRowSkeleton />
          </div>
          <aside className='rounded-card border border-line bg-surface p-5'>
            <h2 className='text-[15px] font-semibold text-ink'>Run trace</h2>
            <div className='mt-5'>
              <TraceSkeleton />
            </div>
          </aside>
        </div>
      ) : activeThread?.loaded ? (
        <Results
          thread={activeThread}
          limits={limits}
          refining={isRefining}
          clarify={clarify}
          onFollowUp={followUp}
          onRefinePlatform={handleRefinePlatform}
          onDismissClarify={dismissClarify}
        />
      ) : (
        <SourceInput
          onGenerate={generate}
          loading={isGenerating}
          error={error}
          threads={threads}
          onSelectThread={selectThread}
        />
      )}
    </div>
  )
}

export default Studio
