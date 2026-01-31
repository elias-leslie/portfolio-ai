import { Card, CardContent } from '@/components/ui/card'

export function StaticSchedulesCard() {
  return (
    <Card className="border-border/50">
      <CardContent className="pt-6">
        <h4 className="mb-3 text-sm font-medium text-text">
          Static Schedules (Not Configurable)
        </h4>
        <ul className="space-y-2 text-xs text-text-muted">
          <li>• Paper Trades Update: Daily at 4:30 PM ET</li>
          <li>• Data Cleanup: Weekly on Sunday 2:00 AM (future)</li>
        </ul>
        <p className="mt-3 text-xs text-text-muted">
          These tasks run on fixed schedules for business logic reasons and
          cannot be customized.
        </p>
      </CardContent>
    </Card>
  )
}
