'use client'

import { useQuery, useQueryClient } from '@tanstack/react-query'
import { type FormEvent, useState } from 'react'
import { useHouseholdIdentity } from '@/components/providers/HouseholdIdentityProvider'
import { Button } from '@/components/ui/button'
import {
  parseComparison,
  parseProducts,
  parseReview,
  parseShelfTags,
  record,
  type ShoppingResult,
} from '@/lib/shopping-pilot'

async function request(path: string, body?: unknown): Promise<unknown> {
  const response = await fetch(
    `/api/captures/shopping/${path}`,
    body === undefined
      ? { cache: 'no-store' }
      : {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
        },
  )
  const value: unknown = await response.json()
  if (!response.ok) {
    const error = record(value)
    throw new Error(
      typeof error.detail === 'string'
        ? error.detail
        : 'Check the required fields and try again.',
    )
  }
  return value
}
const inputClass =
  'mt-1 block w-full min-w-0 rounded-md border border-border bg-bg p-2 text-sm'
function Field({
  name,
  label,
  value,
  type = 'text',
  required = true,
}: {
  name: string
  label: string
  value?: string | number
  type?: string
  required?: boolean
}) {
  return (
    <label className="block text-sm">
      {label}
      <input
        className={inputClass}
        name={name}
        type={type}
        defaultValue={value}
        required={required}
        step={type === 'number' ? 'any' : undefined}
        min={type === 'number' ? 0 : undefined}
        maxLength={type === 'text' ? 500 : undefined}
      />
    </label>
  )
}

export function ShoppingPilot() {
  const identity = useHouseholdIdentity()
  const adult = identity.access !== 'capture_only'
  const [open, setOpen] = useState(false)
  const [selected, setSelected] = useState('')
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const [comparison, setComparison] = useState<ShoppingResult | null>(null)
  const cache = useQueryClient()
  const products = useQuery({
    queryKey: ['shopping-pilot', identity.member_id, 'products'],
    enabled: open,
    queryFn: async () => parseProducts(await request('products')),
  })
  const review = useQuery({
    queryKey: ['shopping-pilot', identity.member_id, 'review'],
    enabled: open && adult,
    queryFn: async () => parseReview(await request('review')),
  })
  const captures = useQuery({
    queryKey: ['shopping-pilot', identity.member_id, 'shelf-tags'],
    enabled: open && adult,
    queryFn: async () => {
      const response = await fetch('/api/captures')
      if (!response.ok) throw new Error('Shelf tags could not be loaded.')
      const value: unknown = await response.json()
      return parseShelfTags(value)
    },
  })
  const product = review.data?.find((row) => row.id === selected)
  async function submit(
    event: FormEvent<HTMLFormElement>,
    kind: 'compare' | 'package' | 'offer' | 'family',
  ) {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    setBusy(true)
    setMessage('')
    setComparison(null)
    try {
      const text = (name: string) => String(form.get(name) ?? '')
      const number = (name: string) => Number(form.get(name))
      if (kind === 'compare') {
        setComparison(
          parseComparison(
            await request('compare', {
              product_id: selected,
              package_label: text('package_label'),
              total_price: number('total_price'),
            }),
          ),
        )
      } else if (kind === 'package') {
        await request(`${selected}/package`, {
          fingerprint: product?.baseline?.fingerprint,
          package_label: text('package_label'),
          packages: number('packages'),
          evidence: text('evidence'),
        })
      } else if (kind === 'offer') {
        await request('offers', {
          product_id: selected,
          capture_id: text('capture_id') || null,
          store: text('store'),
          title: text('title'),
          package_label: text('package_label'),
          price: number('price'),
          fees: number('fees'),
          coupon: number('coupon'),
          observed_date: text('observed_date'),
          valid_until: text('valid_until'),
          conditions: text('conditions'),
          costco_item_number: text('costco_item_number') || null,
          ...Object.fromEntries(
            [
              'availability_confirmed',
              'equivalence_confirmed',
              'membership_confirmed',
              'coupon_confirmed',
              'fees_confirmed',
            ].map((name) => [name, form.get(name) === 'on']),
          ),
        })
      } else {
        await request('families', {
          product_ids: [selected, text('other')],
          name: text('name'),
          purpose: text('purpose'),
        })
      }
      if (kind !== 'compare') {
        await cache.invalidateQueries({ queryKey: ['shopping-pilot'] })
        await cache.invalidateQueries({ queryKey: ['captures'] })
        await cache.invalidateQueries({ queryKey: ['household'] })
        setMessage(
          'Confirmed. This updates price evidence; no purchase was added.',
        )
      }
    } catch (error) {
      setMessage(
        error instanceof Error ? error.message : 'Could not save. Try again.',
      )
    } finally {
      setBusy(false)
    }
  }
  async function withdraw(path: string) {
    setBusy(true)
    setMessage('')
    setComparison(null)
    try {
      await request(path, {})
      await cache.invalidateQueries({ queryKey: ['shopping-pilot'] })
      await cache.invalidateQueries({ queryKey: ['captures'] })
      await cache.invalidateQueries({ queryKey: ['household'] })
      setMessage('Updated. Original purchase amounts are preserved.')
    } catch (error) {
      setMessage(
        error instanceof Error ? error.message : 'Could not update evidence.',
      )
    } finally {
      setBusy(false)
    }
  }
  return (
    <details
      className="rounded-xl border border-border p-4"
      onToggle={(event) => setOpen(event.currentTarget.open)}
    >
      <summary className="cursor-pointer font-semibold">
        Should I buy this? · Staple price check
      </summary>
      {open && (
        <div className="mt-4 space-y-4">
          <p className="text-sm text-text-muted">
            Start with up to 25 repeat purchases. Compare total package
            contents; only adult-confirmed offers from the last 14 days qualify.
            Saving a photo alone does not verify its price.
          </p>
          {products.isPending ? (
            <p>Loading repeat purchases…</p>
          ) : products.error ? (
            <p role="alert">
              Shopping items could not be loaded.{' '}
              <button type="button" onClick={() => void products.refetch()}>
                Retry
              </button>
            </p>
          ) : (
            <label className="block text-sm">
              Item
              <select
                className={inputClass}
                value={selected}
                onChange={(event) => {
                  setSelected(event.target.value)
                  setComparison(null)
                  setMessage('')
                }}
              >
                <option value="">Choose a repeat purchase</option>
                {products.data?.map((row) => (
                  <option key={row.id} value={row.id}>
                    {row.name}
                  </option>
                ))}
              </select>
            </label>
          )}
          {selected && (
            <>
              <form
                key={`compare-${selected}`}
                className="space-y-3"
                onSubmit={(event) => void submit(event, 'compare')}
              >
                <Field
                  name="package_label"
                  label="Contents of the package in front of you (e.g. 2 x 32 fl oz)"
                />
                <Field
                  name="total_price"
                  type="number"
                  label="Price for that entire package, including required fees and usable coupon ($)"
                />
                <Button type="submit" disabled={busy}>
                  Compare recorded offers
                </Button>
              </form>
              {comparison && (
                <div
                  role="status"
                  className="space-y-2 rounded-lg border border-border p-3 text-sm"
                >
                  <p>{comparison.explanation}</p>
                  {comparison.entered_unit_price !== null && (
                    <p>
                      Your entered price: $
                      {comparison.entered_unit_price.toFixed(3)}/
                      {comparison.unit}.
                    </p>
                  )}
                  {comparison.alternative_store && (
                    <>
                      <p>
                        {comparison.alternative_store}: $
                        {comparison.alternative_price?.toFixed(2)} for{' '}
                        {comparison.alternative_package}, observed{' '}
                        {comparison.alternative_date}.
                      </p>
                      <p>
                        {comparison.equivalent_difference
                          ? `$${comparison.equivalent_difference.toFixed(2)} less for equivalent contents. The package at the other store may cost more upfront.`
                          : 'No positive difference for equivalent contents.'}
                      </p>
                      <p>{comparison.conditions}</p>
                    </>
                  )}
                </div>
              )}
              {adult && (
                <details className="border-t border-border pt-3">
                  <summary className="cursor-pointer text-sm font-medium">
                    Review package, shelf tag or substitute
                  </summary>
                  <div className="mt-3 space-y-4">
                    {review.isPending && <p>Loading source evidence…</p>}
                    {review.error && (
                      <p role="alert">
                        Purchase evidence could not be loaded.{' '}
                        <button
                          type="button"
                          onClick={() => void review.refetch()}
                        >
                          Retry
                        </button>
                      </p>
                    )}
                    {product?.offers && product.offers.length > 0 && (
                      <details>
                        <summary className="cursor-pointer text-sm">
                          Recorded offers ({product.offers.length})
                        </summary>
                        <div className="mt-2 space-y-3">
                          {product.offers.map((offer) => (
                            <div
                              key={offer.id}
                              className="space-y-1 rounded-md border border-border p-3 text-sm"
                            >
                              <p>
                                {offer.store} · {offer.title}
                              </p>
                              <p>
                                ${offer.price.toFixed(2)} for{' '}
                                {offer.package_label} · {offer.date}
                              </p>
                              <p>{offer.conditions}</p>
                              <p>
                                {offer.ready
                                  ? 'Confirmed within 14 days'
                                  : 'Expired or withdrawn; excluded from recommendations'}
                              </p>
                              {offer.ready && (
                                <Button
                                  type="button"
                                  size="sm"
                                  variant="outline"
                                  disabled={busy}
                                  onClick={() =>
                                    void withdraw(`offers/${offer.id}/withdraw`)
                                  }
                                >
                                  Withdraw offer
                                </Button>
                              )}
                            </div>
                          ))}
                        </div>
                      </details>
                    )}
                    {product?.purchase_comparison && (
                      <div className="rounded-md border border-border p-3 text-sm">
                        <p>
                          Latest linked receipt: $
                          {product.purchase_comparison.paid.toFixed(2)} on{' '}
                          {product.purchase_comparison.date}.
                        </p>
                        <p>
                          $
                          {Math.abs(
                            product.purchase_comparison.difference,
                          ).toFixed(2)}{' '}
                          {product.purchase_comparison.difference >= 0
                            ? 'less'
                            : 'more'}{' '}
                          than the earlier purchase price for the same contents.
                        </p>
                        <p className="mt-1 text-xs text-text-muted">
                          {product.purchase_comparison.explanation}
                        </p>
                      </div>
                    )}
                    {product?.baseline && (
                      <>
                        <p className="text-sm">
                          Latest purchase: {product.baseline.description} ·{' '}
                          {product.baseline.date} · $
                          {product.baseline.line_total.toFixed(2)} line total.{' '}
                          {product.baseline.unit_price !== null
                            ? `$${product.baseline.unit_price.toFixed(3)}/${product.baseline.unit}.`
                            : 'Package quantity needs confirmation.'}
                        </p>
                        <details>
                          <summary className="cursor-pointer text-sm">
                            Confirm or correct that purchase’s package
                          </summary>
                          <form
                            key={`package-${selected}`}
                            className="mt-3 space-y-3"
                            onSubmit={(event) => void submit(event, 'package')}
                          >
                            <Field
                              name="package_label"
                              label="Contents per purchased package"
                              value={product.baseline.package_label ?? ''}
                            />
                            <Field
                              name="packages"
                              type="number"
                              label="Number of those packages in this purchase"
                              value={product.baseline.packages ?? ''}
                            />
                            <Field
                              name="evidence"
                              label="Source that confirms the size and count"
                            />
                            <Button type="submit" disabled={busy}>
                              Confirm this purchase’s package
                            </Button>
                          </form>
                        </details>
                      </>
                    )}
                    <details>
                      <summary className="cursor-pointer text-sm">
                        Confirm a shelf price
                      </summary>
                      <form
                        key={`offer-${selected}`}
                        className="mt-3 space-y-3"
                        onSubmit={(event) => void submit(event, 'offer')}
                      >
                        <label className="block text-sm">
                          Uploaded shelf tag (optional)
                          <select className={inputClass} name="capture_id">
                            <option value="">
                              Viewed directly; describe evidence below
                            </option>
                            {captures.data?.map((row) => (
                              <option key={row.id} value={row.id}>
                                {row.store_name || 'Shelf tag'} ·{' '}
                                {row.created_at.slice(0, 10)}
                              </option>
                            ))}
                          </select>
                        </label>
                        {captures.error && (
                          <p className="text-sm">
                            Saved shelf tags could not be loaded.
                          </p>
                        )}
                        <Field
                          name="store"
                          label="Store and location"
                          value={product?.stores[0] ?? ''}
                        />
                        <Field
                          name="title"
                          label="Exact item or acceptable substitute on the tag"
                        />
                        <Field
                          name="package_label"
                          label="Total package contents, including multipack"
                        />
                        <Field
                          name="price"
                          type="number"
                          label="Package price ($)"
                        />
                        <Field
                          name="fees"
                          type="number"
                          label="Required delivery or other incremental fees ($; 0 if none)"
                        />
                        <Field
                          name="coupon"
                          type="number"
                          label="Coupon you can use ($; 0 if none)"
                        />
                        <Field
                          name="observed_date"
                          type="date"
                          label="Date you checked the price and stock"
                        />
                        <Field
                          name="valid_until"
                          type="date"
                          label="Valid through: earliest price or coupon expiry (within 14 days of checking)"
                        />
                        <Field
                          name="conditions"
                          label="Source, pickup/delivery, membership and coupon conditions"
                        />
                        <Field
                          name="costco_item_number"
                          label="Costco item number (optional)"
                          required={false}
                        />
                        {(
                          [
                            [
                              'equivalence_confirmed',
                              'This is an acceptable substitute for the selected item, including type, strength and quality.',
                            ],
                            [
                              'availability_confirmed',
                              'The item is available at this store or delivery location.',
                            ],
                            [
                              'membership_confirmed',
                              'The household meets any membership conditions.',
                            ],
                            [
                              'coupon_confirmed',
                              'The coupon amount is usable on this purchase, or there is no coupon.',
                            ],
                            [
                              'fees_confirmed',
                              'All required incremental fees are included above.',
                            ],
                          ] as const
                        ).map(([name, label]) => (
                          <label
                            key={name}
                            className="flex items-start gap-2 text-sm"
                          >
                            <input
                              name={name}
                              type="checkbox"
                              required
                              className="mt-1"
                            />
                            {label}
                          </label>
                        ))}
                        <Button type="submit" disabled={busy}>
                          Confirm offer
                        </Button>
                      </form>
                    </details>
                    <details>
                      <summary className="cursor-pointer text-sm">
                        Group an acceptable substitute
                      </summary>
                      {product?.family && (
                        <p className="mt-2 text-sm">
                          Current group: {product.family.name}.{' '}
                          {product.family.purpose}
                          <button
                            type="button"
                            className="ml-2 underline"
                            disabled={busy}
                            onClick={() => void withdraw(`${selected}/ungroup`)}
                          >
                            Remove this item from group
                          </button>
                        </p>
                      )}
                      <form
                        key={`family-${selected}`}
                        className="mt-3 space-y-3"
                        onSubmit={(event) => void submit(event, 'family')}
                      >
                        <label className="block text-sm">
                          Other repeat purchase
                          <select name="other" className={inputClass} required>
                            <option value="">Choose a substitute</option>
                            {products.data
                              ?.filter((row) => row.id !== selected)
                              .map((row) => (
                                <option key={row.id} value={row.id}>
                                  {row.name}
                                </option>
                              ))}
                          </select>
                        </label>
                        <Field name="name" label="Comparison group name" />
                        <Field
                          name="purpose"
                          label="Why these are equivalent for this household (type, strength, quality and purpose)"
                        />
                        <p className="text-xs text-text-muted">
                          Both packages must have matching content units. This
                          replaces the selected items’ current groups; products
                          remain distinct.
                        </p>
                        <Button type="submit" disabled={busy}>
                          Confirm these substitutes
                        </Button>
                      </form>
                    </details>
                  </div>
                </details>
              )}
            </>
          )}
          {message && (
            <p role="status" className="text-sm">
              {message}
            </p>
          )}
        </div>
      )}
    </details>
  )
}
