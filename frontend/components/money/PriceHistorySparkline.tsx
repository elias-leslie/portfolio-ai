'use client'

import { useState } from 'react'
import type { HouseholdProductPricePoint } from '@/lib/api/household'
import { formatCurrency } from '@/lib/formatters'
import { cn } from '@/lib/utils'
import { formatLedgerDate } from './ledger-helpers'

interface PriceHistorySparklineProps {
  points: HouseholdProductPricePoint[]
  width?: number
  height?: number
  className?: string
}

/**
 * Purchase-price sparkline with a hover tooltip carrying the full observation
 * detail (date, vendor, price, quantity, unit price). Points arrive oldest
 * first from the products endpoint.
 */
export function PriceHistorySparkline({
  points,
  width = 120,
  height = 32,
  className,
}: PriceHistorySparklineProps) {
  const [activeIndex, setActiveIndex] = useState<number | null>(null)

  if (points.length === 0) {
    return <span className="text-xs text-text-muted">No history</span>
  }

  const pointPrice = (point: HouseholdProductPricePoint) =>
    point.unitPrice ?? point.totalPrice
  const prices = points.map(pointPrice)
  const minPrice = Math.min(...prices)
  const maxPrice = Math.max(...prices)
  const priceRange = maxPrice - minPrice
  const pad = 4
  const coords = points.map((point, index) => ({
    x:
      points.length === 1
        ? width / 2
        : pad + (index / (points.length - 1)) * (width - pad * 2),
    y:
      priceRange === 0
        ? height / 2
        : height -
          pad -
          ((pointPrice(point) - minPrice) / priceRange) * (height - pad * 2),
  }))
  const pathData = coords
    .map((coord, index) => `${index === 0 ? 'M' : 'L'} ${coord.x},${coord.y}`)
    .join(' ')
  const rising = prices[prices.length - 1] > prices[0]
  const falling = prices[prices.length - 1] < prices[0]
  // Price up is the bad direction here, unlike portfolio sparklines.
  const strokeClass = rising
    ? 'stroke-loss'
    : falling
      ? 'stroke-gain'
      : 'stroke-viz-3'

  const active = activeIndex !== null ? points[activeIndex] : null
  const activeCoord = activeIndex !== null ? coords[activeIndex] : null

  function handleMove(event: React.MouseEvent<SVGSVGElement>) {
    const bounds = event.currentTarget.getBoundingClientRect()
    const x = event.clientX - bounds.left
    let nearest = 0
    for (let index = 1; index < coords.length; index += 1) {
      if (Math.abs(coords[index].x - x) < Math.abs(coords[nearest].x - x)) {
        nearest = index
      }
    }
    setActiveIndex(nearest)
  }

  return (
    <div className={cn('relative inline-block', className)}>
      <svg
        width={width}
        height={height}
        className="overflow-visible"
        role="img"
        aria-label={`Price history, ${points.length} purchases, latest ${formatCurrency(
          prices[prices.length - 1],
          { decimals: 2 },
        )}${points[points.length - 1]?.unitPrice != null ? ' per unit' : ''}`}
        onMouseMove={handleMove}
        onMouseLeave={() => setActiveIndex(null)}
      >
        <path
          d={pathData}
          fill="none"
          className={strokeClass}
          strokeWidth={1.5}
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        {activeCoord ? (
          <circle
            cx={activeCoord.x}
            cy={activeCoord.y}
            r={3}
            className="fill-text"
          />
        ) : (
          <circle
            cx={coords[coords.length - 1].x}
            cy={coords[coords.length - 1].y}
            r={2.5}
            className="fill-text-muted"
          />
        )}
      </svg>
      {active && activeCoord ? (
        <div
          data-testid="price-point-tooltip"
          className="pointer-events-none absolute bottom-full z-50 mb-1 w-max max-w-[220px] -translate-x-1/2 rounded-lg border border-border/50 bg-surface px-3 py-2 text-xs shadow-xl"
          style={{ left: activeCoord.x }}
        >
          <p className="font-medium text-text">
            {formatLedgerDate(active.observedDate)}
            {active.merchant ? ` · ${active.merchant}` : ''}
          </p>
          <p className="mt-0.5 font-mono tabular-nums text-text">
            {formatCurrency(active.totalPrice, { decimals: 2 })}
            {active.quantity != null && active.quantity !== 1
              ? ` · qty ${active.quantity}`
              : ''}
            {active.unitPrice != null
              ? ` · ${formatCurrency(active.unitPrice, { decimals: 2 })}/unit`
              : ''}
          </p>
        </div>
      ) : null}
    </div>
  )
}
