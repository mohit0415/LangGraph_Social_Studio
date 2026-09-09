import { metaFor } from './platforms'

export const STEP_STYLE = {
  brief: { icon: 'pi-file-edit', tone: 'text-brand' },
  write: { icon: 'pi-pencil', tone: 'text-muted' },
  self_check: { icon: 'pi-search', tone: 'text-muted' },
  accept: { icon: 'pi-check-circle', tone: 'text-emerald-600' },
  consistency: { icon: 'pi-sync', tone: 'text-brand' },
  refine: { icon: 'pi-sparkles', tone: 'text-brand' },
}

export const STATUS_TONE = {
  ok: 'text-emerald-600',
  accepted: 'text-emerald-600',
  problem: 'text-amber-600',
  accepted_as_is: 'text-amber-600',
  revised: 'text-amber-600',
  fixed: 'text-brand',
  refined: 'text-brand',
}

export const STEP_LABEL = {
  brief: 'Brief',
  write: 'Write',
  self_check: 'Self-check',
  accept: 'Accept',
  consistency: 'Consistency',
  refine: 'Refine',
}

export const actorLabel = (actor) => {
  if (actor === 'manager') return 'Manager'
  if (actor === 'consistency') return 'Consistency'
  return metaFor(actor).label
}

export const formatDuration = (ms) => {
  if (ms == null) return null
  return ms >= 1000 ? `${(ms / 1000).toFixed(1)}s` : `${ms}ms`
}

export const orderEvents = (events = []) =>
  [...events].sort((a, b) => (a.ts - b.ts) || (a.stage - b.stage))

export const groupByActor = (events = []) => {
  const groups = []
  const index = {}

  orderEvents(events).forEach((ev) => {
    if (!index[ev.actor]) {
      index[ev.actor] = { actor: ev.actor, events: [] }
      groups.push(index[ev.actor])
    }
    index[ev.actor].events.push(ev)
  })

  const rank = (a) => (a.actor === 'manager' ? 0 : a.actor === 'consistency' ? 2 : 1)
  return groups.sort((a, b) => rank(a) - rank(b))
}

export const summarise = (events = []) => {
  const attempts = events.reduce((max, e) => Math.max(max, e.attempt || 0), 0)
  const totalMs = events.reduce((sum, e) => sum + (e.duration_ms || 0), 0)
  return { attempts, totalMs }
}
