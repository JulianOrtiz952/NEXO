import test from 'node:test'
import assert from 'node:assert/strict'
import { groupMenuProducts } from './menuGroups.js'

test('RF-031: category identity controls grouping and server order survives', () => {
  const products = [
    { id: 'p1', category: 'b', category_name: 'Especiales' },
    { id: 'p2', category: 'a', category_name: 'Especiales' },
    { id: 'p3', category: 'b', category_name: 'Especiales' },
  ]
  const before = structuredClone(products)
  const groups = groupMenuProducts(products)
  assert.deepEqual(groups.map(group => group.id), ['b', 'a'])
  assert.deepEqual(groups.map(group => group.products.map(product => product.id)), [['p1', 'p3'], ['p2']])
  assert.deepEqual(products, before)
  assert.deepEqual(groupMenuProducts([]), [])
})
