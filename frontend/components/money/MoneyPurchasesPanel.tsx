'use client'

import { useDeferredValue, useEffect, useState } from 'react'
import { LoadErrorState } from '@/components/shared/LoadErrorState'
import { SectionCard } from '@/components/shared/SectionCard'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import type { HouseholdPriceInsight } from '@/lib/api/household'
import {
  useHouseholdProducts,
  usePriceCheckStatus,
  usePurchaseItemReviewQueue,
  usePurchaseItems,
  useTriggerPriceCheck,
} from '@/lib/hooks/useHouseholdPurchases'
import { PriceCheckStatusCard } from './PriceCheckStatusCard'
import { PriceSignalsTable } from './PriceSignalsTable'
import { ProductCatalogTable } from './ProductCatalogTable'
import { ProductDetailSheet } from './ProductDetailSheet'
import { ProductMatchReviewCard } from './ProductMatchReviewCard'
import { PurchaseFindingsList } from './PurchaseFindingsList'
import { PurchaseItemsOwnerTable } from './PurchaseItemsOwnerTable'
import { ShoppingListsCard } from './ShoppingListsCard'
import { useCategoryOwnerMap } from './useCategoryOwnerMap'

const PRODUCT_PAGE_SIZE = 50
const ITEM_PAGE_SIZE = 50

type ProductSort = 'recent' | 'frequency' | 'name'

const productSorts: Array<{ value: ProductSort; label: string }> = [
  { value: 'recent', label: 'Recent' },
  { value: 'frequency', label: 'Most bought' },
  { value: 'name', label: 'A-Z' },
]

interface MoneyPurchasesPanelProps {
  priceInsights: HouseholdPriceInsight[]
}

export function MoneyPurchasesPanel({
  priceInsights,
}: MoneyPurchasesPanelProps) {
  const [search, setSearch] = useState('')
  const [itemSearch, setItemSearch] = useState('')
  const [sort, setSort] = useState<ProductSort>('recent')
  const [currentPage, setCurrentPage] = useState(1)
  const [itemPage, setItemPage] = useState(1)
  const [openProductId, setOpenProductId] = useState<string | null>(null)
  const deferredSearch = useDeferredValue(search.trim())
  const deferredItemSearch = useDeferredValue(itemSearch.trim())
  const offset = (currentPage - 1) * PRODUCT_PAGE_SIZE
  const itemOffset = (itemPage - 1) * ITEM_PAGE_SIZE
  const categoryOwnerMap = useCategoryOwnerMap()

  const {
    data: catalog,
    isLoading,
    error,
    refetch,
    isFetching,
  } = useHouseholdProducts({
    search: deferredSearch || undefined,
    sort,
    limit: PRODUCT_PAGE_SIZE,
    offset,
  })
  const { data: reviewQueue } = usePurchaseItemReviewQueue()
  const {
    data: purchaseItems,
    isLoading: isLoadingItems,
    error: itemError,
    refetch: refetchItems,
    isFetching: isFetchingItems,
  } = usePurchaseItems({
    search: deferredItemSearch || undefined,
    limit: ITEM_PAGE_SIZE,
    offset: itemOffset,
  })
  const { data: priceCheck } = usePriceCheckStatus()
  const triggerPriceCheck = useTriggerPriceCheck()

  useEffect(() => {
    setCurrentPage(1)
  }, [deferredSearch, sort])

  useEffect(() => {
    setItemPage(1)
  }, [deferredItemSearch])

  const totalCount = catalog?.totalCount ?? 0
  const totalPages = Math.max(1, Math.ceil(totalCount / PRODUCT_PAGE_SIZE))
  const boundedPage = Math.min(currentPage, totalPages)
  const pageStart = totalCount === 0 ? 0 : offset + 1
  const pageEnd = offset + (catalog?.returnedCount ?? 0)
  const itemTotalCount = purchaseItems?.totalCount ?? 0
  const itemTotalPages = Math.max(1, Math.ceil(itemTotalCount / ITEM_PAGE_SIZE))
  const boundedItemPage = Math.min(itemPage, itemTotalPages)
  const itemPageStart = itemTotalCount === 0 ? 0 : itemOffset + 1
  const itemPageEnd = itemOffset + (purchaseItems?.returnedCount ?? 0)

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

  return (
    <div className="space-y-6">
      <SectionCard
        variant="surface"
        title="Receipt / invoice items"
        description="Set the owner directly on each item. Category owners fill the dropdown by default; choosing a name saves an item-level override."
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <Input
              value={itemSearch}
              onChange={(event) => setItemSearch(event.target.value)}
              placeholder="Search item, product, or vendor"
              aria-label="Search purchase items"
              className="w-[260px]"
            />
            <Button
              type="button"
              size="sm"
              variant="outline"
              onClick={() => {
                void refetchItems()
              }}
              disabled={isFetchingItems}
            >
              Refresh
            </Button>
          </div>
        }
      >
        {itemError ? (
          <LoadErrorState
            title="Failed to load purchase items."
            detail="Retry to refresh receipt and invoice item rows."
            onRetry={() => {
              void refetchItems()
            }}
            isRetrying={isFetchingItems}
          />
        ) : (
          <>
            <PurchaseItemsOwnerTable
              items={purchaseItems?.items ?? []}
              isLoading={isLoadingItems}
              hasData={Boolean(purchaseItems)}
              categoryOwnerMap={categoryOwnerMap}
            />
            <div className="mt-3 flex flex-col gap-3 text-xs text-text-muted md:flex-row md:items-center md:justify-between">
              <span>
                Showing {itemPageStart}-{itemPageEnd} of {itemTotalCount} item
                {itemTotalCount === 1 ? '' : 's'}
              </span>
              <div className="flex items-center gap-2">
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  disabled={boundedItemPage <= 1}
                  onClick={() => setItemPage((page) => Math.max(1, page - 1))}
                >
                  Previous
                </Button>
                <span>
                  Page {boundedItemPage} of {itemTotalPages}
                </span>
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  disabled={boundedItemPage >= itemTotalPages}
                  onClick={() =>
                    setItemPage((page) => Math.min(itemTotalPages, page + 1))
                  }
                >
                  Next
                </Button>
              </div>
            </div>
          </>
        )}
      </SectionCard>

      <SectionCard
        variant="surface"
        title="Product Catalog"
        description="Every product seen on receipts and order history, with the price you actually paid over time. Hover a trend line for purchase detail."
        actions={
          <div className="flex flex-wrap items-center gap-2">
            {productSorts.map((option) => (
              <Button
                key={option.value}
                type="button"
                size="sm"
                variant={sort === option.value ? 'default' : 'outline'}
                onClick={() => setSort(option.value)}
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
