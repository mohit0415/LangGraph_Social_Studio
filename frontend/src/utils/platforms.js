export const PLATFORM_META = {
  linkedin: { label: 'LinkedIn', dot: 'bg-[#0a66c2]', maxChars: 3000 },
  x: { label: 'X', dot: 'bg-ink', maxChars: 280 },
  instagram: { label: 'Instagram', dot: 'bg-[#e1306c]', maxChars: 2200 },
}

export const metaFor = (id) =>
  PLATFORM_META[id] || { label: id, dot: 'bg-subtle', maxChars: null }

export const formatCount = (n) => n.toLocaleString('en-US').replace(/,/g, ' ')

export const parseTrace = (trace = []) => {
  const groups = []
  const index = {}

  trace.forEach((line) => {
    const match = /^\[([^\]]+)\]\s*(.*)$/.exec(line)
    const key = match ? match[1] : 'run'
    const text = match ? match[2] : line

    if (!index[key]) {
      index[key] = { key, lines: [] }
      groups.push(index[key])
    }
    index[key].lines.push(text)
  })

  return groups
}

export const isProblemLine = (text) =>
  /self-check:\s*(?!OK)\S/i.test(text) || /too long|out of attempts/i.test(text)

export const isGoodLine = (text) => /self-check:\s*OK/i.test(text)

export const chipFor = (platform, trace = []) => {
  const mine = trace.filter((l) => l.toLowerCase().startsWith(`[${platform}]`))
  if (mine.length === 0) return null

  if (mine.some((l) => /refined on request/i.test(l))) return 'refined on request'
  if (mine.some((l) => /out of attempts/i.test(l))) return 'accepted as-is'

  const accepted = mine.find((l) => /accepted after (\d+)/i.test(l))
  const attempts = accepted ? Number(/accepted after (\d+)/i.exec(accepted)[1]) : 0

  if (attempts <= 1) return 'clean on first pass'

  const reason = /too long/i.test(mine.join(' ')) ? 'length' : 'self-check'
  return `${attempts} attempts · ${reason}`
}
