import { Card, CardContent, CardHeader } from '@/components/ui/card'

export function AccountsWithPositionsSkeleton() {
  return (
    <Card data-testid="accounts-with-positions-skeleton">
      <CardHeader>
        <div className="space-y-2">
          <div className="skeleton rounded-md h-5 w-60" />
          <div className="skeleton rounded-md h-3 w-48" />
        </div>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          {[0, 1].map((item) => (
            <div
              key={`account-with-positions-skeleton-${item}`}
              className="rounded-2xl border border-border/50 bg-surface/40 p-4"
            >
              <div className="flex items-center justify-between">
                <div className="space-y-2">
                  <div className="skeleton h-4 w-48" />
                  <div className="skeleton h-3 w-32" />
                </div>
                <div className="skeleton rounded-full h-10 w-10" />
              </div>
              <div className="mt-4 space-y-2">
                {[0, 1, 2].map((row) => (
                  <div
                    key={`account-with-positions-skeleton-row-${item}-${row}`}
                    className="skeleton rounded-lg h-10 w-full"
                  />
                ))}
              </div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}
