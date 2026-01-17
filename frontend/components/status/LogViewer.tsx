'use client'

import { Check, Copy } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { ScrollArea } from '@/components/ui/scroll-area'

interface LogViewerProps {
  lines: string[]
  isLoading?: boolean
  error?: Error | null
}

export function LogViewer({ lines, isLoading, error }: LogViewerProps) {
  const [copied, setCopied] = useState(false)
  const [autoScroll, setAutoScroll] = useState(true)
  const scrollRef = useRef<HTMLDivElement>(null)

  // Auto-scroll to bottom when new logs arrive
  useEffect(() => {
    if (autoScroll && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [autoScroll])

  const handleCopy = async () => {
    await navigator.clipboard.writeText(lines.join('\n'))
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  // Syntax highlighting for log levels
  const getLineStyle = (line: string): string => {
    if (line.includes('ERROR') || line.includes('[error]')) {
      return 'text-loss'
    }
    if (line.includes('WARN') || line.includes('[warn]')) {
      return 'text-warning'
    }
    if (line.includes('INFO') || line.includes('[info]')) {
      return 'text-accent'
    }
    return 'text-text-muted'
  }

  if (error) {
    return (
      <Alert variant="destructive">
        <AlertDescription>
          {error.message.includes('404')
            ? 'Log file not found'
            : error.message.includes('403')
              ? 'Permission denied'
              : `Error loading logs: ${error.message}`}
        </AlertDescription>
      </Alert>
    )
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center p-4">
        <div className="text-sm text-muted-foreground">Loading logs...</div>
      </div>
    )
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-2">
          <Checkbox
            id="auto-scroll"
            checked={autoScroll}
            onCheckedChange={(checked) => setAutoScroll(checked as boolean)}
          />
          <label
            htmlFor="auto-scroll"
            className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
          >
            Auto-scroll
          </label>
        </div>
        <Button variant="outline" size="sm" onClick={handleCopy}>
          {copied ? (
            <>
              <Check className="mr-2 h-4 w-4" />
              Copied
            </>
          ) : (
            <>
              <Copy className="mr-2 h-4 w-4" />
              Copy
            </>
          )}
        </Button>
      </div>

      <ScrollArea className="h-[400px] w-full rounded-md border bg-bg p-4">
        <div ref={scrollRef} className="space-y-1">
          {lines.length === 0 ? (
            <div className="text-sm text-muted-foreground">
              No logs available
            </div>
          ) : (
            lines.map((line, idx) => (
              <div
                key={idx}
                className={`font-mono text-xs ${getLineStyle(line)}`}
              >
                {line}
              </div>
            ))
          )}
        </div>
      </ScrollArea>
    </div>
  )
}
