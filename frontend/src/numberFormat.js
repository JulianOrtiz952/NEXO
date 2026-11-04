// RF-024, RNF-033: presentation never converts canonical decimal strings to float.
export function groupInteger(value) {
  const blocks = String(value).match(/\d{1,6}(?=(\d{6})*$)/g) || ['0']
  return blocks.map(block => block.replace(/\B(?=(\d{3})+(?!\d))/g, ',')).join("'")
}

export function formatQuantity(value) {
  const match = String(value).match(/^(-?)(\d+)(?:\.(\d+))?$/)
  if (!match) return String(value)
  return match[1] + groupInteger(match[2]) + (match[3] ? '.' + match[3] : '')
}

export function formatMoney(value) {
  return '$ ' + formatQuantity(value)
}

export function parseAmount(value) {
  const raw = String(value).replace(/[,'’]/g, '')
  if (!/^\d{1,10}(?:\.\d{0,2})?$/.test(raw)) return null
  const [integer, fraction] = raw.split('.')
  return integer.replace(/^0+(?=\d)/, '') + (fraction !== undefined ? '.' + fraction : '')
}

export function formatAmountInput(value) {
  const canonical = parseAmount(value)
  if (canonical === null) return null
  const [integer, fraction] = canonical.split('.')
  return groupInteger(integer) + (fraction !== undefined ? '.' + fraction : '')
}
