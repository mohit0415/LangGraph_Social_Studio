import React from 'react'
import BriefCard from '../components/BriefCard'
import PostCard from '../components/PostCard'
import TracePanel from '../components/TracePanel'
import ChatBar from '../components/ChatBar'
import { BriefSkeleton, PostsRowSkeleton } from '../components/Skeletons'
import { chipFor } from '../utils/platforms'
import { shortId } from '../components/ThreadDropdown'

const Results = ({
  thread,
  limits,
  refining,
  clarify,
  onFollowUp,
  onRefinePlatform,
  onDismissClarify,
}) => {
  const platforms = Object.keys(thread.posts || {})

  return (
    <div className='mx-auto grid max-w-[1440px] gap-6 px-4 py-6 sm:px-6 lg:grid-cols-[1fr_320px] xl:grid-cols-[1fr_340px]'>
      <div className='min-w-0 space-y-6'>
        <p className='flex flex-wrap items-center gap-x-2 gap-y-1 text-[12.5px] text-subtle'>
          <span className='font-mono text-ink'>{shortId(thread.id)}</span>
          <span>·</span>
          <span className='max-w-[420px] truncate'>{thread.title}</span>
        </p>

        {refining ? <BriefSkeleton /> : <BriefCard brief={thread.brief} />}

        {refining ? (
          <PostsRowSkeleton />
        ) : (
          <div className='grid gap-4 sm:grid-cols-2 lg:grid-cols-3'>
            {platforms.map((platform) => (
              <PostCard
                key={platform}
                platform={platform}
                text={thread.posts[platform]}
                maxChars={limits?.[platform]}
                chip={chipFor(platform, thread.trace)}
                refining={refining}
                onRefine={onRefinePlatform}
              />
            ))}
          </div>
        )}

        {thread.messages?.length > 0 && (
          <div className='space-y-2'>
            {thread.messages.map((msg, i) =>
              msg.role === 'user' ? (
                <div key={i} className='flex justify-end'>
                  <p className='max-w-[80%] rounded-card bg-brand px-3.5 py-2 text-[13.5px] text-white'>
                    {msg.text}
                  </p>
                </div>
              ) : (
                <p key={i} className='px-1 text-[12.5px] leading-[1.5] text-subtle'>
                  {msg.text}
                </p>
              ),
            )}
          </div>
        )}

        <ChatBar
          onSend={onFollowUp}
          busy={refining}
          clarify={clarify}
          onDismissClarify={onDismissClarify}
        />
      </div>

      <TracePanel trace={thread.trace} events={thread.events} loading={refining} />
    </div>
  )
}

export default Results
