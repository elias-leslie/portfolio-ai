import type { Thesis } from '@/lib/api/thesis'

export function ValueDriversSection({
  drivers,
}: {
  drivers: NonNullable<Thesis['valueDrivers']>
}) {
  const items = [
    { label: 'Market Size', value: drivers.marketSize },
    { label: 'Company Position', value: drivers.companyPosition },
    { label: 'Upside Potential', value: drivers.upsidePotential },
    { label: 'Competitive Moat', value: drivers.competitiveMoat },
  ].filter((item) => item.value !== null)

  if (items.length === 0) return null

  return (
    <div className="border-t border-border pt-3 space-y-2">
      <h5 className="text-xs font-semibold text-text">Value Drivers</h5>
      <div className="grid grid-cols-2 gap-2">
        {items.map((item) => (
          <div key={item.label} className="bg-surface-muted/50 rounded px-2 py-1.5">
            <p className="text-xs text-text-muted">{item.label}</p>
            <p className="text-sm font-medium text-text">{item.value}</p>
          </div>
        ))}
      </div>
    </div>
  )
}
