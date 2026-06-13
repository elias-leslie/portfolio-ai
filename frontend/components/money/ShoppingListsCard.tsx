'use client'

import { useEffect, useMemo, useState } from 'react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Switch } from '@/components/ui/switch'
import { Textarea } from '@/components/ui/textarea'
import type {
  HouseholdShoppingList,
  HouseholdVendorProfile,
} from '@/lib/api/household'
import { formatCurrency, formatEnumLabel } from '@/lib/formatters'
import {
  useCreateShoppingList,
  useImportShoppingListItems,
  useOptimizeShoppingList,
  useShoppingLists,
  useUpdateVendorProfiles,
  useVendorProfiles,
} from '@/lib/hooks/useHouseholdPurchases'

type VendorBasket = {
  vendor_key?: string
  vendorKey?: string
  display_name?: string
  displayName?: string
  item_count?: number
  itemCount?: number
  uncovered_count?: number
  uncoveredCount?: number
  subtotal?: number
  fees?: number
  total?: number
}

type SplitRecommendation = {
  recommended?: boolean
  savings?: number
  threshold?: number
  subtotal?: number
  fees?: number
  total?: number
  assignments?: Array<{
    name?: string
    vendor_key?: string
    vendorKey?: string
    price?: number
    substitution_flag?: boolean
    substitutionFlag?: boolean
  }>
}

type Optimization = {
  item_count?: number
  itemCount?: number
  matched_item_count?: number
  matchedItemCount?: number
  uncovered_items?: string[]
  uncoveredItems?: string[]
  stale_quote_items?: string[]
  staleQuoteItems?: string[]
  vendor_baskets?: VendorBasket[]
  vendorBaskets?: VendorBasket[]
  best_single_vendor?: VendorBasket | null
  bestSingleVendor?: VendorBasket | null
  split_recommendation?: SplitRecommendation | null
  splitRecommendation?: SplitRecommendation | null
}

function currency(value: unknown) {
  return formatCurrency(typeof value === 'number' ? value : 0, { decimals: 2 })
}

function listItemLabel(list: HouseholdShoppingList) {
  const count = list.items.filter((item) => item.status === 'open').length
  return `${count} open item${count === 1 ? '' : 's'}`
}

function optimization(list: HouseholdShoppingList): Optimization | null {
  const raw = list.latestOptimization
  if (!raw || typeof raw !== 'object') return null
  return raw as Optimization
}

function vendorKey(basket: VendorBasket) {
  return basket.vendorKey ?? basket.vendor_key ?? 'vendor'
}

function vendorName(basket: VendorBasket) {
  return (
    basket.displayName ??
    basket.display_name ??
    formatEnumLabel(vendorKey(basket))
  )
}

function basketItemCount(basket: VendorBasket) {
  return basket.itemCount ?? basket.item_count ?? 0
}

function uncoveredCount(basket: VendorBasket) {
  return basket.uncoveredCount ?? basket.uncovered_count ?? 0
}

function profileDraftKey(vendor: HouseholdVendorProfile) {
  return vendor.vendorKey
}

export function ShoppingListsCard() {
  const { data: listsData, isLoading } = useShoppingLists()
  const { data: vendorData } = useVendorProfiles()
  const createList = useCreateShoppingList()
  const importItems = useImportShoppingListItems()
  const optimizeList = useOptimizeShoppingList()
  const updateProfiles = useUpdateVendorProfiles()
  const [newListName, setNewListName] = useState('Groceries')
  const [importListId, setImportListId] = useState<string | null>(null)
  const [importText, setImportText] = useState('')
  const [vendorDrafts, setVendorDrafts] = useState<
    Record<string, HouseholdVendorProfile>
  >({})

  const lists = listsData?.lists ?? []
  const activeList = lists[0]
  const activeOptimization = activeList ? optimization(activeList) : null
  const vendorBaskets =
    activeOptimization?.vendorBaskets ??
    activeOptimization?.vendor_baskets ??
    []
  const bestSingle =
    activeOptimization?.bestSingleVendor ??
    activeOptimization?.best_single_vendor
  const split =
    activeOptimization?.splitRecommendation ??
    activeOptimization?.split_recommendation
  const uncovered =
    activeOptimization?.uncoveredItems ??
    activeOptimization?.uncovered_items ??
    []
  const stale =
    activeOptimization?.staleQuoteItems ??
    activeOptimization?.stale_quote_items ??
    []

  useEffect(() => {
    if (!vendorData?.vendors) return
    setVendorDrafts(
      Object.fromEntries(
        vendorData.vendors.map((vendor) => [profileDraftKey(vendor), vendor]),
      ),
    )
  }, [vendorData?.vendors])

  const draftVendors = useMemo(
    () =>
      Object.values(vendorDrafts).sort((a, b) =>
        a.vendorKey.localeCompare(b.vendorKey),
      ),
    [vendorDrafts],
  )

  function updateVendorDraft(
    vendorKeyValue: string,
    patch: Partial<HouseholdVendorProfile>,
  ) {
    setVendorDrafts((current) => ({
      ...current,
      [vendorKeyValue]: {
        ...current[vendorKeyValue],
        ...patch,
      },
    }))
  }

  async function submitImport() {
    if (!importListId || !importText.trim()) return
    await importItems.mutateAsync({
      listId: importListId,
      text: importText.trim(),
    })
    setImportText('')
    setImportListId(null)
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-3 rounded-2xl border border-border/40 bg-surface/45 p-4 md:flex-row md:items-end md:justify-between">
        <div className="space-y-1">
          <p className="text-sm font-semibold text-text">Create a list</p>
          <p className="text-xs text-text-muted">
            Paste groceries or household supplies, then optimize from stored
            vendor quotes.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Input
            value={newListName}
            onChange={(event) => setNewListName(event.target.value)}
            aria-label="New shopping list name"
            className="w-[220px]"
          />
          <Button
            type="button"
            size="sm"
            onClick={() => createList.mutate({ name: newListName, items: [] })}
            disabled={createList.isPending || !newListName.trim()}
          >
            Create list
          </Button>
        </div>
      </div>

      {isLoading ? (
        <p className="text-sm text-text-muted">Loading shopping lists…</p>
      ) : lists.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-border/40 bg-surface-muted/10 p-6">
          <p className="text-sm font-semibold text-text">
            No shopping lists yet.
          </p>
          <p className="mt-2 text-sm text-text-muted">
            Create one, paste a grocery list, and Jenny will match known
            products before optimizing.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {lists.map((list) => (
            <div
              key={list.id}
              className="rounded-2xl border border-border/40 bg-surface/45 p-4"
            >
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="font-medium text-text">{list.name}</p>
                  <p className="text-xs text-text-muted">
                    {listItemLabel(list)}
                  </p>
                </div>
                <div className="flex flex-wrap gap-2">
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    onClick={() => setImportListId(list.id)}
                  >
                    Import items
                  </Button>
                  <Button
                    type="button"
                    size="sm"
                    onClick={() => optimizeList.mutate(list.id)}
                    disabled={optimizeList.isPending || list.items.length === 0}
                  >
                    Optimize
                  </Button>
                </div>
              </div>
              {list.items.length > 0 && (
                <ul className="mt-3 grid gap-2 md:grid-cols-2">
                  {list.items.slice(0, 8).map((item) => (
                    <li
                      key={item.id}
                      className="rounded-xl bg-surface-muted/10 px-3 py-2 text-sm text-text"
                    >
                      {item.productName ?? item.freeText ?? 'Item'}
                      {item.quantity ? (
                        <span className="ml-2 text-xs text-text-muted">
                          {item.quantity} {item.unit ?? ''}
                        </span>
                      ) : null}
                      {item.productId ? (
                        <Badge variant="success" className="ml-2">
                          matched
                        </Badge>
                      ) : (
                        <Badge variant="warning" className="ml-2">
                          free text
                        </Badge>
                      )}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          ))}
        </div>
      )}

      {activeList && activeOptimization && (
        <div className="rounded-2xl border border-border/40 bg-surface/45 p-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="text-sm font-semibold text-text">
                Latest optimization: {activeList.name}
              </p>
              <p className="text-xs text-text-muted">
                {activeOptimization.matchedItemCount ??
                  activeOptimization.matched_item_count ??
                  0}{' '}
                matched of{' '}
                {activeOptimization.itemCount ??
                  activeOptimization.item_count ??
                  0}{' '}
                open items.
              </p>
            </div>
            {split?.recommended ? (
              <Badge variant="success">
                Split saves {currency(split.savings)}
              </Badge>
            ) : (
              <Badge variant="warning">Single vendor preferred</Badge>
            )}
          </div>

          {bestSingle && (
            <p className="mt-3 text-sm text-text">
              Best single vendor:{' '}
              <span className="font-medium">{vendorName(bestSingle)}</span> ·{' '}
              {basketItemCount(bestSingle)} items · total{' '}
              {currency(bestSingle.total)}
            </p>
          )}

          {vendorBaskets.length > 0 && (
            <div className="mt-3 grid gap-2 md:grid-cols-3">
              {vendorBaskets.slice(0, 3).map((basket) => (
                <div
                  key={vendorKey(basket)}
                  className="rounded-xl bg-surface-muted/10 p-3"
                >
                  <p className="text-sm font-medium text-text">
                    {vendorName(basket)}
                  </p>
                  <p className="mt-1 text-xs text-text-muted">
                    {basketItemCount(basket)} covered · {uncoveredCount(basket)}{' '}
                    uncovered
                  </p>
                  <p className="mt-2 text-sm text-text">
                    {currency(basket.total)}{' '}
                    <span className="text-xs text-text-muted">incl. fees</span>
                  </p>
                </div>
              ))}
            </div>
          )}

          {split?.assignments && split.assignments.length > 0 && (
            <div className="mt-3 rounded-xl bg-surface-muted/10 p-3">
              <p className="text-xs font-semibold uppercase tracking-wide text-text-muted">
                Split basket
              </p>
              <ul className="mt-2 space-y-1 text-sm text-text-muted">
                {split.assignments.slice(0, 6).map((assignment, index) => (
                  <li key={`${assignment.name ?? 'item'}-${index}`}>
                    {assignment.name} →{' '}
                    {formatEnumLabel(
                      assignment.vendorKey ?? assignment.vendor_key ?? '',
                    )}{' '}
                    ({currency(assignment.price)})
                    {assignment.substitutionFlag || assignment.substitution_flag
                      ? ' · check substitute'
                      : ''}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {(uncovered.length > 0 || stale.length > 0) && (
            <p className="mt-3 text-xs text-text-muted">
              {uncovered.length > 0
                ? `Uncovered: ${uncovered.join(', ')}. `
                : ''}
              {stale.length > 0 ? `Stale quotes: ${stale.join(', ')}.` : ''}
            </p>
          )}
        </div>
      )}

      {draftVendors.length > 0 && (
        <div className="rounded-2xl border border-border/40 bg-surface/45 p-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="text-sm font-semibold text-text">Vendor profiles</p>
              <p className="text-xs text-text-muted">
                Fees and membership settings are user-configured, not scraped.
              </p>
            </div>
            <Button
              type="button"
              size="sm"
              variant="outline"
              onClick={() => updateProfiles.mutate({ vendors: draftVendors })}
              disabled={updateProfiles.isPending}
            >
              Save vendor profiles
            </Button>
          </div>
          <div className="mt-3 grid gap-3 md:grid-cols-3">
            {draftVendors.map((vendor) => (
              <div
                key={vendor.vendorKey}
                className="rounded-xl bg-surface-muted/10 p-3"
              >
                <div className="flex items-center justify-between gap-2">
                  <p className="text-sm font-medium text-text">
                    {vendor.displayName}
                  </p>
                  <Switch
                    checked={vendor.enabled}
                    onCheckedChange={(checked) =>
                      updateVendorDraft(vendor.vendorKey, { enabled: checked })
                    }
                    aria-label={`Enable ${vendor.displayName}`}
                  />
                </div>
                <div className="mt-3 grid grid-cols-2 gap-2">
                  <Input
                    aria-label={`${vendor.displayName} delivery fee`}
                    type="number"
                    min="0"
                    step="0.01"
                    value={vendor.deliveryFee ?? ''}
                    onChange={(event) =>
                      updateVendorDraft(vendor.vendorKey, {
                        deliveryFee: event.target.value
                          ? Number(event.target.value)
                          : null,
                      })
                    }
                  />
                  <Input
                    aria-label={`${vendor.displayName} free delivery threshold`}
                    type="number"
                    min="0"
                    step="0.01"
                    value={vendor.freeDeliveryThreshold ?? ''}
                    onChange={(event) =>
                      updateVendorDraft(vendor.vendorKey, {
                        freeDeliveryThreshold: event.target.value
                          ? Number(event.target.value)
                          : null,
                      })
                    }
                  />
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      <Dialog
        open={importListId !== null}
        onOpenChange={(open) => !open && setImportListId(null)}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Import shopping items</DialogTitle>
            <DialogDescription>
              Paste a list. Jenny returns JSON items; unmatched items stay free
              text.
            </DialogDescription>
          </DialogHeader>
          <Textarea
            value={importText}
            onChange={(event) => setImportText(event.target.value)}
            placeholder="milk\neggs\n2 bags edamame"
            aria-label="Shopping list text"
            rows={8}
          />
          <div className="flex justify-end gap-2">
            <Button
              type="button"
              variant="outline"
              onClick={() => setImportListId(null)}
            >
              Cancel
            </Button>
            <Button
              type="button"
              onClick={() => {
                void submitImport()
              }}
              disabled={importItems.isPending || !importText.trim()}
            >
              Import
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  )
}
