import React, { useState } from 'react'
import { metaFor, parseTrace, isProblemLine, isGoodLine } from '../utils/platforms'
import {
  STEP_STYLE,
  STEP_LABEL,
  STATUS_TONE,
  actorLabel,
  formatDuration,
  orderEvents,
  groupByActor,
  summarise,
} from '../utils/traceEvents'
import { TraceSkeleton } from './Skeletons'

const TABS = [
  { id: 'steps', label: 'By platform' },
  { id: 'timeline', label: 'Timeline' },
]

const DETAIL_CLAMP = 180

const EventRow = ({ ev, showActor = false }) => {
  const [expanded, setExpanded] = useState(false)
  const step = STEP_STYLE[ev.step] || { icon: 'pi-circle', tone: 'text-muted' }
  const tone = STATUS_TONE[ev.status] || 'text-muted'
  const duration = formatDuration(ev.duration_ms)

  const detail = ev.detail || ''
  const isLong = detail.length > DETAIL_CLAMP
  const shown = isLong && !expanded ? `${detail.slice(0, DETAIL_CLAMP)}…` : detail

  return (
    <li className='flex gap-2.5'>
      <div className='flex flex-col items-center'>
        <i className={`pi ${step.icon} text-[11px] ${tone}`} />
        <span className='mt-1 w-px flex-1 bg-line' />
      </div>

      <div className='min-w-0 flex-1 pb-3'>
        <div className='flex flex-wrap items-center gap-x-2 gap-y-0.5'>
          <span className='text-[12.5px] font-medium text-ink'>
            {STEP_LABEL[ev.step] || ev.step}
          </span>

          {showActor && (
            <span className='text-[11.5px] text-subtle'>{actorLabel(ev.actor)}</span>
          )}

          {ev.attempt != null && (
            <span className='rounded-full bg-canvas px-1.5 text-[10.5px] text-subtle'>
              attempt {ev.attempt}
            </span>
          )}

          {duration && (
            <span className='text-[10.5px] tabular-nums text-subtle'>{duration}</span>
          )}
        </div>

        <p className={`mt-0.5 text-[12px] leading-[1.45] break-words ${tone}`}>
          {shown}
          {isLong && (
            <button
              type='button'
              onClick={() => setExpanded(!expanded)}
              className='ml-1 text-brand hover:underline'
            >
              {expanded ? 'less' : 'more'}
            </button>
          )}
        </p>
      </div>
    </li>
  )
}

const TracePanel = ({ trace = [], events = [], loading = false }) => {
  const [tab, setTab] = useState('steps')
  const hasEvents = events.length > 0

  return (
    <aside className='rounded-card border border-line bg-surface p-5 lg:sticky lg:top-24 lg:max-h-[calc(100vh-7rem)] lg:overflow-y-auto'>
      <h2 className='text-[15px] font-semibold text-ink'>Run trace</h2>
      <p className='mt-1.5 text-[12.5px] leading-[1.5] text-subtle'>
        Every step each writer took. The three platforms run at the same time, so
        the timeline is interleaved.
      </p>

      {hasEvents && !loading && (
        <div className='mt-4 flex gap-1 rounded-field bg-canvas p-1'>
          {TABS.map((t) => (
            <button
              key={t.id}
              type='button'
              onClick={() => setTab(t.id)}
              className={`flex-1 rounded-[7px] px-2 py-1.5 text-[12px] transition-colors ${
                tab === t.id
                  ? 'bg-surface font-medium text-ink shadow-[0_1px_2px_rgba(17,20,24,0.06)]'
                  : 'text-subtle hover:text-ink'
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>
      )}

      <div className='mt-4'>
        {loading ? (
          <TraceSkeleton />
        ) : hasEvents ? (
          tab === 'timeline' ? (
            <ul className='space-y-0'>
              {orderEvents(events).map((ev, i) => (
                <EventRow key={i} ev={ev} showActor />
              ))}
            </ul>
          ) : (
            <div className='space-y-3'>
              {groupByActor(events).map((group) => {
                const isPlatform = !['manager', 'consistency'].includes(group.actor)
                const meta = metaFor(group.actor)
                const { attempts, totalMs } = summarise(group.events)

                return (
                  <div key={group.actor} className='rounded-field bg-canvas p-3'>
                    <div className='flex items-center gap-2'>
                      {isPlatform ? (
                        <span className={`h-2 w-2 rounded-full ${meta.dot}`} />
                      ) : (
                        <i className='pi pi-cog text-[10px] text-brand' />
                      )}
                      <span className='text-[13px] font-medium text-ink'>
                        {actorLabel(group.actor)}
                      </span>
                      <div className='flex-1' />
                      {attempts > 0 && (
                        <span className='text-[11px] text-subtle'>
                          {attempts} attempt{attempts > 1 ? 's' : ''}
                        </span>
                      )}
                      {totalMs > 0 && (
                        <span className='text-[11px] tabular-nums text-subtle'>
                          {formatDuration(totalMs)}
                        </span>
                      )}
                    </div>

                    <ul className='mt-2.5'>
                      {group.events.map((ev, i) => (
                        <EventRow key={i} ev={ev} />
                      ))}
                    </ul>
                  </div>
                )
              })}
            </div>
          )
        ) : trace.length > 0 ? (
          <div className='space-y-3'>
            {parseTrace(trace).map((group) => (
              <div key={group.key} className='rounded-field bg-canvas p-3'>
                <span className='text-[13px] font-medium text-ink'>
                  {actorLabel(group.key)}
                </span>
                <ul className='mt-2 space-y-1.5'>
                  {group.lines.map((line, i) => (
                    <li
                      key={i}
                      className={`flex gap-2 text-[12.5px] leading-[1.45] ${
                        isProblemLine(line)
                          ? 'text-amber-600'
                          : isGoodLine(line)
                            ? 'text-emerald-600'
                            : 'text-muted'
                      }`}
                    >
                      <span className='select-none text-subtle'>·</span>
                      <span>{line}</span>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        ) : (
          <p className='text-[13px] text-subtle'>No trace for this thread yet.</p>
        )}
      </div>
    </aside>
  )
}

export default TracePanel
