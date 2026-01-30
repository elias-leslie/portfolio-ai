import {
  Card,
  CardContent,
  CardHeader,
} from '@/components/ui/card'

export function AccountsWithPositionsSkeleton() {
  return (
    <Card data-testid="accounts-with-positions-skeleton">
      <CardHeader>
        <div className="space-y-2">
          <div className="h-5 w-60 animate-pulse rounded-md bg-surface-muted/60" />
          <div className="h-3 w-48 animate-pulse rounded-md bg-surface-muted/40" />
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
                  <div className="h-4 w-48 animate-pulse rounded bg-surface-muted/80" />
                  <div className="h-3 w-32 animate-pulse rounded bg-surface-muted/60" />
                </div>
                <div className="h-10 w-10 rounded-full bg-surface-muted/60" />
              </div>
              <div className="mt-4 space-y-2">
                {[0, 1, 2].map((row) => (
                  <div
                    key={`account-with-positions-skeleton-row-${item}-${row}`}
                    className="h-10 w-full animate-pulse rounded-lg bg-surface-muted/50"
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
