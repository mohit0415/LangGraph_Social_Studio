import React, { useState } from 'react'
import { metaFor, formatCount } from '../utils/platforms'

const HASHTAG_SPLIT = /(#[\p{L}\p{N}_]+)/u
const HASHTAG_EXACT = /^#[\p{L}\p{N}_]+$/u

const highlightHashtags = (text) =>
  text
    .split(HASHTAG_SPLIT)
    .map((part, i) =>
      HASHTAG_EXACT.test(part) ? (
        <span key={i} className='text-brand font-bold italic'>
          {part}
        </span>
      ) : (
        part
      ),
    )

const PostCard = ({ platform, text = '', maxChars, chip, onRefine, refining }) => {
  const meta = metaFor(platform)
  const limit = maxChars ?? meta.maxChars
  const [copied, setCopied] = useState(false)

  const over = limit != null && text.length > limit

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(text)
      setCopied(true)
      setTimeout(() => setCopied(false), 1600)
    } catch {
      setCopied(false)
    }
  }

  return (
    <article className='flex flex-col rounded-card border border-line bg-surface p-4 sm:p-[18px] transition-shadow hover:shadow-[0_4px_20px_rgba(17,20,24,0.06)]'>
      <header className='flex items-center gap-3'>
        <span className={`h-2.5 w-2.5 shrink-0 rounded-full ${meta.dot}`} />
        <h3 className='text-[15px] font-semibold text-ink'>{meta.label}</h3>
        <div className='flex-1' />
        <span
          className={`text-[12px] tabular-nums ${over ? 'font-semibold text-red-600' : 'text-subtle'}`}
        >
          {formatCount(text.length)}
          {limit != null && ` / ${formatCount(limit)}`}
        </span>
      </header>

      {chip && (
        <span className='mt-3 w-fit rounded-full bg-canvas px-2.5 py-1 text-[12px] text-muted'>
          {chip}
        </span>
      )}

      <div className='my-4 h-px w-full bg-line' />

      <div className='min-h-[120px] flex-1 whitespace-pre-wrap text-[13.5px] leading-[1.6] text-ink'>
        {text ? highlightHashtags(text) : <span className='text-subtle'>No draft yet.</span>}
      </div>

      <footer className='mt-5 flex gap-2'>
        <button
          type='button'
          onClick={handleCopy}
          className='inline-flex items-center gap-1.5 rounded-field border border-line px-3.5 py-2 text-[13px] text-ink transition-colors hover:border-brand hover:text-brand'
        >
          <i className={`pi ${copied ? 'pi-check' : 'pi-copy'} text-[12px]`} />
          {copied ? 'Copied' : 'Copy'}
        </button>

        <button
          type='button'
          onClick={() => onRefine?.(platform)}
          disabled={refining}
          className='inline-flex items-center gap-1.5 rounded-field border border-line px-3.5 py-2 text-[13px] text-ink transition-colors hover:border-brand hover:text-brand disabled:opacity-40'
        >
          <i className='pi pi-pencil text-[12px]' />
          Refine
        </button>
      </footer>
    </article>
  )
}

export default PostCard
