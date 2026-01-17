'use client'

import { Card, CardContent } from '@/components/ui/card'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'

interface DisplaySettingsProps {
  displayTimezone: string
  onDisplayTimezoneChange: (value: string) => void
}

export const TIMEZONE_OPTIONS = {
  'America/New_York': 'Eastern Time (EST/EDT)',
  'America/Chicago': 'Central Time (CST/CDT)',
  'America/Denver': 'Mountain Time (MST/MDT)',
  'America/Los_Angeles': 'Pacific Time (PST/PDT)',
  'America/Anchorage': 'Alaska Time (AKST/AKDT)',
  'Pacific/Honolulu': 'Hawaii Time (HST)',
}

export function DisplaySettings({
  displayTimezone,
  onDisplayTimezoneChange,
}: DisplaySettingsProps) {
  return (
    <div className="space-y-6">
      {/* Timezone */}
      <Card>
        <CardContent className="pt-6">
          <div className="space-y-2">
            <Label htmlFor="timezone">Timezone</Label>
            <Select
              value={displayTimezone}
              onValueChange={onDisplayTimezoneChange}
            >
              <SelectTrigger id="timezone">
                <SelectValue placeholder="Select timezone" />
              </SelectTrigger>
              <SelectContent>
                {Object.entries(TIMEZONE_OPTIONS).map(([value, label]) => (
                  <SelectItem key={value} value={value}>
                    {label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <p className="text-xs text-text-muted">
              Choose your preferred timezone for displaying dates and times
              throughout the application
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
