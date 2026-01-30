import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '@/components/ui/accordion'
import { Badge } from '@/components/ui/badge'
import { formatTimestamp } from '../ExpandedRowUtils'

export function VersionHistorySection({
  versions,
  userTimezone,
}: {
  versions: Array<{
    version: number
    status: string
    action: string
    createdAt: string
  }>
  userTimezone: string
}) {
  return (
    <div className="border-t border-border pt-3">
      <Accordion type="single" collapsible>
        <AccordionItem value="history" className="border-0">
          <AccordionTrigger className="hover:no-underline py-2 text-xs font-semibold">
            Version History ({versions.length})
          </AccordionTrigger>
          <AccordionContent>
            <div className="space-y-2 pt-2">
              {versions.map((version) => (
                <div
                  key={version.version}
                  className="flex items-center justify-between text-xs border-b border-border pb-2 last:border-0"
                >
                  <div className="flex items-center gap-2">
                    <Badge variant="outline" className="text-xs">
                      v{version.version}
                    </Badge>
                    <span className="text-text-muted">{version.action}</span>
                    <Badge variant="outline" className="text-xs">
                      {version.status}
                    </Badge>
                  </div>
                  <span className="text-text-muted">
                    {formatTimestamp(version.createdAt, userTimezone)}
                  </span>
                </div>
              ))}
            </div>
          </AccordionContent>
        </AccordionItem>
      </Accordion>
    </div>
  )
}
