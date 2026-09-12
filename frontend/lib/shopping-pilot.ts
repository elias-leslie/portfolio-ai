/** Validate the narrow capture API before rendering a price or source. */
export type PilotProduct = { id: string; name: string; stores: string[] }
export type PilotReview = PilotProduct & {
  offers: {
    id: string
    price: number
    package_label: string
    date: string
    store: string
    title: string
    conditions: string
    ready: boolean
  }[]
  purchase_comparison: {
    date: string
    paid: number
    difference: number
    transaction_id: string
    explanation: string
  } | null
  family: { name: string; purpose: string } | null
  baseline: {
    fingerprint: string
    description: string
    date: string
    line_total: number
    packages: number | null
    package_label: string | null
    unit_price: number | null
    unit: string | null
  } | null
}
export type ShoppingResult = {
  explanation: string
  entered_unit_price: number | null
  unit: string | null
  alternative_store: string | null
  alternative_package: string | null
  alternative_price: number | null
  alternative_date: string | null
  equivalent_difference: number | null
  conditions: string | null
}
export function record(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value))
    throw new Error('Shopping evidence could not be read.')
  return value as Record<string, unknown>
}
function string(value: unknown): string {
  if (typeof value !== 'string')
    throw new Error('Shopping text could not be read.')
  return value
}
function number(value: unknown): number {
  if (typeof value !== 'number' || !Number.isFinite(value))
    throw new Error('Shopping price could not be read.')
  return value
}
function nullable<T>(value: unknown, parse: (item: unknown) => T): T | null {
  return value == null ? null : parse(value)
}
function array<T>(value: unknown, parse: (item: unknown) => T): T[] {
  if (!Array.isArray(value)) throw new Error('Shopping list could not be read.')
  return value.map(parse)
}
function product(value: unknown): PilotProduct {
  const row = record(value)
  return {
    id: string(row.id),
    name: string(row.name),
    stores: array(row.stores, string),
  }
}
export function parseProducts(value: unknown): PilotProduct[] {
  return array(value, product)
}
export function parseReview(value: unknown): PilotReview[] {
  return array(value, (value) => {
    const row = record(value)
    return {
      ...product(row),
      offers: array(row.offers, (value) => {
        const row = record(value)
        if (typeof row.ready !== 'boolean')
          throw new Error('Offer status could not be read.')
        return {
          id: string(row.id),
          price: number(row.price),
          package_label: string(row.package_label),
          date: string(row.date),
          store: string(row.store),
          title: string(row.title),
          conditions: string(row.conditions),
          ready: row.ready,
        }
      }),
      purchase_comparison: nullable(row.purchase_comparison, (value) => {
        const row = record(value)
        return {
          date: string(row.date),
          paid: number(row.paid),
          difference: number(row.difference),
          transaction_id: string(row.transaction_id),
          explanation: string(row.explanation),
        }
      }),
      family: nullable(row.family, (value) => {
        const row = record(value)
        return { name: string(row.name), purpose: string(row.purpose) }
      }),
      baseline: nullable(row.baseline, (value) => {
        const row = record(value)
        return {
          fingerprint: string(row.fingerprint),
          description: string(row.description),
          date: string(row.date),
          line_total: number(row.line_total),
          packages: nullable(row.packages, number),
          package_label: nullable(row.package_label, string),
          unit_price: nullable(row.unit_price, number),
          unit: nullable(row.unit, string),
        }
      }),
    }
  })
}
export function parseComparison(value: unknown): ShoppingResult {
  const row = record(value)
  return {
    explanation: string(row.explanation),
    entered_unit_price: nullable(row.entered_unit_price, number),
    unit: nullable(row.unit, string),
    alternative_store: nullable(row.alternative_store, string),
    alternative_package: nullable(row.alternative_package, string),
    alternative_price: nullable(row.alternative_price, number),
    alternative_date: nullable(row.alternative_date, string),
    equivalent_difference: nullable(row.equivalent_difference, number),
    conditions: nullable(row.conditions, string),
  }
}
export function parseShelfTags(value: unknown) {
  return array(value, (value) => {
    const row = record(value)
    return {
      id: string(row.id),
      kind: string(row.kind),
      store_name: string(row.store_name),
      created_at: string(row.created_at),
    }
  }).filter((row) => row.kind === 'shelf_tag')
}
