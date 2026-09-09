import React from 'react'
import ChatBox from '../components/ChatBox'
import { shortId } from '../components/ThreadDropdown'

const SAMPLES = [
  {
    label: 'Engineering post-mortem',
    text: 'We spent three weeks upgrading the model to fix a latency problem. The bug turned out to be one layer down, in how we were batching requests. Rebuilding the agent as six sequential function calls dropped costs 71% and took p95 latency from 30s to 4s.',
  },
  {
    label: 'Product launch note',
    text: 'We shipped a new scheduling view this week. It replaces the old list with a week grid, supports drag to reschedule, and syncs to Google Calendar in under two seconds. Early users cut their planning time roughly in half.',
  },
  {
    label: 'Research finding',
    text: 'A study of 1,200 engineering teams found that teams shipping daily had 40% fewer production incidents than teams shipping monthly. The mechanism was smaller change sets, not better testing.',
  },
]

const SourceInput = ({ onGenerate, loading, error, threads = [], onSelectThread }) => {
  return (
    <main className='flex flex-col items-center px-4 sm:px-6 pt-14 sm:pt-20 lg:pt-24 pb-16'>
      <div className='flex flex-col items-center gap-2.5 text-center'>
        <h1 className='font-bold text-ink leading-[1.2] text-[28px] sm:text-[32px] lg:text-[34px]'>
          One idea. Three platforms.
        </h1>
        <p className='max-w-[620px] text-[15px] leading-[1.45] text-muted'>
          Paste an article, a transcript, or a rough idea. The studio writes,
          critiques and reconciles a post for LinkedIn, X and Instagram.
        </p>
      </div>

      {error && (
        <div className='mt-6 flex w-full max-w-[760px] items-start gap-2.5 rounded-card border border-red-200 bg-red-50 p-4'>
          <i className='pi pi-exclamation-circle mt-0.5 text-[13px] text-red-600' />
          <p className='text-[13.5px] text-red-700'>{error}</p>
        </div>
      )}

      <div className='mt-7 flex w-full justify-center'>
        <ChatBox onSubmit={onGenerate} loading={loading} />
      </div>

      <div className='mt-10 w-full max-w-[760px]'>
        <p className='text-[13px] font-medium text-subtle'>Or start from a sample</p>

        <div className='mt-3 grid gap-2.5 sm:grid-cols-3'>
          {SAMPLES.map((sample) => (
            <button
              key={sample.label}
              type='button'
              disabled={loading}
              onClick={() => onGenerate(sample.text)}
              className='group flex items-center justify-between gap-2 rounded-field border border-line bg-surface px-3.5 py-3 text-left text-[14px] text-ink transition-all hover:border-brand hover:shadow-[0_2px_10px_rgba(31,111,235,0.10)] disabled:opacity-50'
            >
              <span className='truncate'>{sample.label}</span>
              <i className='pi pi-arrow-right text-[11px] text-subtle transition-colors group-hover:text-brand' />
            </button>
          ))}
        </div>
      </div>

      {threads.length > 0 && (
        <div className='mt-10 w-full max-w-[760px]'>
          <p className='text-[13px] font-medium text-subtle'>
            Or continue an earlier thread
          </p>

          <div className='mt-3 flex flex-wrap gap-2'>
            {threads.map((thread) => (
              <button
                key={thread.id}
                type='button'
                onClick={() => onSelectThread(thread.id)}
                className='group flex max-w-full items-center gap-2 rounded-full border border-line bg-surface px-3 py-1.5 text-[12.5px] text-muted transition-colors hover:border-brand hover:text-brand'
              >
                <i className='pi pi-comments text-[11px]' />
                <span className='max-w-[220px] truncate'>{thread.title}</span>
                <span className='font-mono text-[11px] text-subtle group-hover:text-brand'>
                  {shortId(thread.id)}
                </span>
              </button>
            ))}
          </div>
        </div>
      )}
    </main>
  )
}

export default SourceInput
