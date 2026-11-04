import { test } from 'node:test'
import assert from 'node:assert/strict'
import { formatQuantity, formatMoney, formatAmountInput, parseAmount } from './numberFormat.js'

test('RF-024: visible amounts preserve cents and approved separators', () => {
  for (const [raw, visible] of [['0', '0'], ['1000', '1,000'], ['11999.85', '11,999.85'], ['1000000.50', "1'000,000.50"], ['9999999999.99', "9,999'999,999.99"]]) {
    assert.equal(formatQuantity(raw), visible)
    assert.equal(formatMoney(raw), '$ ' + visible)
    assert.equal(parseAmount(visible), raw)
  }
})

test('RF-024: editable amounts preserve unfinished decimals and reject invalid paste', () => {
  assert.equal(formatAmountInput('1000.'), '1,000.')
  assert.equal(formatAmountInput('1000.0'), '1,000.0')
  assert.equal(parseAmount("1'234,567.89"), '1234567.89')
  for (const value of ['-1', '12abc', '1e3', '1.234', '10000000000', '1.2.3']) assert.equal(parseAmount(value), null)
})
