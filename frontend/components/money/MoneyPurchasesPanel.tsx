'use client'

import { useDeferredValue, useEffect, useState } from 'react'
import { LoadErrorState } from '@/components/shared/LoadErrorState'
import { SectionCard } from '@/components/shared/SectionCard'
import {
  nextSortDirection,
  type SortDirection,
} from '@/components/shared/SortableTableHeader'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import type { HouseholdPriceInsight } from '@/lib/api/household'
import {
  useHouseholdProducts,
  usePriceCheckStatus,
  usePurchaseItemReviewQueue,
  useTriggerPriceCheck,
} from '@/lib/hooks/useHouseholdPurchases'
import { BuyGuideCard } from './BuyGuideCard'
import { PriceCheckStatusCard } from './PriceCheckStatusCard'
import { PriceSignalsTable } from './PriceSignalsTable'
import {
  type ProductCatalogScope,
  type ProductCatalogSort,
  ProductCatalogTable,
} from './ProductCatalogTable'
import { ProductDetailSheet } from './ProductDetailSheet'
import { ProductMatchReviewCard } from './ProductMatchReviewCard'
import { PurchaseFindingsList } from './PurchaseFindingsList'
import { ShoppingListsCard } from './ShoppingListsCard'

const PRODUCT_PAGE_SIZE = 50

const productScopes: Array<{ value: ProductCatalogScope; label: string }> = [
  { value: 'active', label: 'Active' },
  { value: 'archived', label: 'Archived' },
  { value: 'all', label: 'All' },
]

interface MoneyPurchasesPanelProps {
  priceInsights: HouseholdPriceInsight[]
}

export function MoneyPurchasesPanel({
  priceInsights,
}: MoneyPurchasesPanelProps) {
  const [search, setSearch] = useState('')
  const [sort, setSort] = useState<ProductCatalogSort>('recent')
  const [sortDirection, setSortDirection] = useState<SortDirection>('desc')
  const [scope, setScope] = useState<ProductCatalogScope>('active')
  const [currentPage, setCurrentPage] = useState(1)
  const [openProductId, setOpenProductId] = useState<string | null>(null)
  const deferredSearch = useDeferredValue(search.trim())
  const offset = (currentPage - 1) * PRODUCT_PAGE_SIZE

  const {
    data: catalog,
    isLoading,
    error,
    refetch,
    isFetching,
  } = useHouseholdProducts({
    search: deferredSearch || undefined,
    sort,
    sortDir: sortDirection,
    scope,
    limit: PRODUCT_PAGE_SIZE,
    offset,
  })
  const { data: reviewQueue } = usePurchaseItemReviewQueue()
  const { data: priceCheck } = usePriceCheckStatus()
  const triggerPriceCheck = useTriggerPriceCheck()

  useEffect(() => {
    setCurrentPage(1)
  }, [deferredSearch, scope, sort, sortDirection])

  const totalCount = catalog?.totalCount ?? 0
  const totalPages = Math.max(1, Math.ceil(totalCount / PRODUCT_PAGE_SIZE))
  const boundedPage = Math.min(currentPage, totalPages)
  const pageStart = totalCount === 0 ? 0 : offset + 1
  const pageEnd = offset + (catalog?.returnedCount ?? 0)

  if (error) {
    return (
      <LoadErrorState
        title="Failed to load purchases."
        detail="Retry to refresh the product catalog and price history."
        onRetry={() => {
          void refetch()
        }}
        isRetrying={isFetching}
      />
    )
  }

  function defaultSortDirection(field: ProductCatalogSort): SortDirection {
    return field === 'name' || field === 'owner' ? 'asc' : 'desc'
  }

  function handleSort(field: ProductCatalogSort) {
    setSortDirection((current) =>
      nextSortDirection(sort, field, current, defaultSortDirection(field)),
    )
    setSort(field)
  }

  return (
    <div className="space-y-6">
      <SectionCard
        variant="surface"
        title="Buy Guide"
        description="Recurring products ranked by actual unit cost: find when a larger package or another vendor beats the size you usually buy."
      >
        <BuyGuideCard onOpenProduct={setOpenProductId} />
      </SectionCard>

      <SectionCard
        variant="surface"
        title="Product Catalog"
        description="Active shows products seen in the last 18 months; Archived keeps older receipt/order-history evidence without crowding routine planning."
        actions={
          <div className="flex flex-wrap items-center gap-2">
            {productScopes.map((option) => (
              <Button
                key={option.value}
                type="button"
                size="sm"
                variant={scope === option.value ? 'default' : 'outline'}
                onClick={() => setScope(option.value)}
              >
                {option.label}
              </Button>
            ))}
            <Input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search product or brand"
              aria-label="Search products"
              className="w-[240px]"
            />
            <Button
              type="button"
              size="sm"
              variant="outline"
              onClick={() => {
                void refetch()
              }}
              disabled={isFetching}
            >
              Refresh
            </Button>
          </div>
        }
      >
        <ProductCatalogTable
          products={catalog?.products ?? []}
          isLoading={isLoading}
          hasData={Boolean(catalog)}
          scope={scope}
          sortKey={sort}
          sortDirection={sortDirection}
          onSort={handleSort}
          onOpenProduct={setOpenProductId}
        />
        <div className="mt-3 flex flex-col gap-3 text-xs text-text-muted md:flex-row md:items-center md:justify-between">
          <span>
            Showing {pageStart}-{pageEnd} of {totalCount} product
            {totalCount === 1 ? '' : 's'}
          </span>
          <div className="flex items-center gap-2">
            <Button
              type="button"
              size="sm"
              variant="outline"
              disabled={boundedPage <= 1}
              onClick={() => setCurrentPage((page) => Math.max(1, page - 1))}
            >
              Previous
            </Button>
            <span>
              Page {boundedPage} of {totalPages}
            </span>
            <Button
              type="button"
              size="sm"
              variant="outline"
              disabled={boundedPage >= totalPages}
              onClick={() =>
                setCurrentPage((page) => Math.min(totalPages, page + 1))
              }
            >
              Next
            </Button>
          </div>
        </div>
      </SectionCard>

      <SectionCard
        variant="surface"
        title="Product Match Review"
        description="Items whose product match was low confidence. Confirm, reassign, or detach — confirmed links sharpen price history."
      >
        <ProductMatchReviewCard
          items={reviewQueue?.items ?? []}
          totalCount={reviewQueue?.totalCount ?? 0}
        />
      </SectionCard>

      <SectionCard
        variant="surface"
        title="Cross-Vendor Price Checks"
        description="Jenny checks Amazon, Walmart, and Publix for your most-bought products. Findings stay in this tab — they never page you."
      >
        <div className="space-y-4">
          <PriceCheckStatusCard
            latestRun={priceCheck?.latestRun}
            onRun={() => triggerPriceCheck.mutate()}
            isTriggering={triggerPriceCheck.isPending}
          />
          <PurchaseFindingsList findings={priceCheck?.openFindings ?? []} />
        </div>
      </SectionCard>

      <SectionCard
        variant="surface"
        title="Shopping Lists"
        description="Paste a list, match it to your product catalog, and optimize against fresh vendor quotes with your fee settings."
      >
        <ShoppingListsCard />
      </SectionCard>

      <SectionCard
        variant="surface"
        title="Price Signals"
        description="Order-history evidence only. Ticket or unit drift belongs here, not in ledger totals."
      >
        {priceInsights.length > 0 ? (
          <PriceSignalsTable rows={priceInsights} />
        ) : (
          <div className="rounded-2xl border border-dashed border-border/40 bg-surface-muted/10 p-6">
            <p className="text-sm font-semibold text-text">
              No price-drift evidence yet.
            </p>
            <p className="mt-2 text-sm text-text-muted">
              Add receipt or order-history evidence and this section will flag
              ticket creep, unit-price jumps, and shrinkflation before they
              silently harden.
            </p>
          </div>
        )}
      </SectionCard>

      <ProductDetailSheet
        productId={openProductId}
        onClose={() => setOpenProductId(null)}
      />
    </div>
  )
}
