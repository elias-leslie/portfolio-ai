import * as React from "react"

import { cn } from "@/lib/utils"

function Textarea({ className, ...props }: React.ComponentProps<"textarea">) {
  return (
    <textarea
      data-slot="textarea"
      className={cn(
        "w-full min-w-0 rounded-md border border-border bg-surface/70 px-3 py-2 text-base text-text shadow-xs transition-all duration-200 ease-in-out outline-none placeholder:text-text-muted selection:bg-primary/80 selection:text-primary-foreground focus-visible:border-focus focus-visible:ring-2 focus-visible:ring-focus/30 disabled:pointer-events-none disabled:cursor-not-allowed disabled:opacity-35 md:text-sm resize-y",
        "aria-invalid:border-destructive aria-invalid:ring-2 aria-invalid:ring-destructive/25",
        className
      )}
      {...props}
    />
  )
}

export { Textarea }
