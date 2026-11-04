// RF-031: preserve the server's category order and group by identity, never by label.
export function groupMenuProducts(products) {
  const groups = new Map()
  for (const product of products) {
    if (!groups.has(product.category)) groups.set(product.category, { id: product.category, name: product.category_name, products: [] })
    groups.get(product.category).products.push(product)
  }
  return [...groups.values()]
}
