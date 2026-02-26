'use client'

import type { KeyEvent } from './types'

interface KeyEventsSectionProps {
  keyEvents: KeyEvent[]
}

export function KeyEventsSection({ keyEvents }: KeyEventsSectionProps) {
  if (!keyEvents || keyEvents.length === 0) return null

  return (
    <div>
      <h5 className="text-xs font-semibold text-text mb-2">Key Events:</h5>
      <div className="space-y-2">
        {keyEvents.map((event, idx) => (
          <div
            key={`event-${idx}-${event.text.substring(0, 20)}`}
            className="flex items-start gap-2 text-xs"
          >
            <span className="text-base flex-shrink-0">{event.icon}</span>
            <div className="flex-1">
              <span className="text-text">{event.text}</span>
              <span className="text-text-muted ml-2">({event.timeAgo})</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
