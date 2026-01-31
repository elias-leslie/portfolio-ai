import { ChevronDown, ChevronRight, Database, RefreshCw } from 'lucide-react'
import { useState } from 'react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible'
import { Progress } from '@/components/ui/progress'
import type { DatabaseSize } from './types'

export function DatabaseSizeCard({
  database,
  isLoading,
}: {
  database: DatabaseSize | null
  isLoading: boolean
}) {
  const [isExpanded, setIsExpanded] = useState(false)

  if (isLoading && !database) {
    return (
      <Card className="border-border">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Database className="h-5 w-5" />
            Database Size
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center py-8">
            <RefreshCw className="h-5 w-5 animate-spin text-muted-foreground" />
          </div>
        </CardContent>
      </Card>
    )
  }

  if (!database) {
    return (
      <Card className="border-border">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Database className="h-5 w-5" />
            Database Size
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            No database information available
          </p>
        </CardContent>
      </Card>
    )
  }

  const topTables = [...database.tables]
    .sort((a, b) => b.sizeMb - a.sizeMb)
    .slice(0, 5)

  const totalTableSize = database.tables.reduce((sum, t) => sum + t.sizeMb, 0)

  return (
    <Card className="border-border">
      <CardHeader>
        <CardTitle className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Database className="h-5 w-5" />
            <span>Database Size</span>
          </div>
          <Badge variant="outline">{database.sizeMb.toFixed(1)} MB</Badge>
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <p className="text-muted-foreground">Database</p>
              <p className="text-lg font-semibold">{database.databaseName}</p>
            </div>
            <div>
              <p className="text-muted-foreground">Total Size</p>
              <p className="text-lg font-semibold">
                {database.sizeMb.toFixed(1)} MB
              </p>
            </div>
          </div>

          <Collapsible open={isExpanded} onOpenChange={setIsExpanded}>
            <CollapsibleTrigger asChild>
              <Button variant="outline" className="w-full justify-between">
                <span>Top Tables ({topTables.length})</span>
                {isExpanded ? (
                  <ChevronDown className="h-4 w-4" />
                ) : (
                  <ChevronRight className="h-4 w-4" />
                )}
              </Button>
            </CollapsibleTrigger>
            <CollapsibleContent>
              <div className="mt-3 space-y-3">
                {topTables.map((table) => (
                  <div
                    key={table.name}
                    className="border rounded-lg p-3 space-y-2"
                  >
                    <div className="flex items-center justify-between">
                      <p className="font-mono text-sm font-medium">
                        {table.name}
                      </p>
                      <Badge variant="secondary">
                        {table.sizeMb.toFixed(1)} MB
                      </Badge>
                    </div>
                    <div className="flex items-center justify-between text-xs text-muted-foreground">
                      <span>{table.rows.toLocaleString()} rows</span>
                      <span>
                        {((table.sizeMb / totalTableSize) * 100).toFixed(1)}% of
                        total
                      </span>
                    </div>
                    <Progress
                      value={(table.sizeMb / totalTableSize) * 100}
                      className="h-1.5"
                    />
                  </div>
                ))}
              </div>
            </CollapsibleContent>
          </Collapsible>
        </div>
      </CardContent>
    </Card>
  )
}
