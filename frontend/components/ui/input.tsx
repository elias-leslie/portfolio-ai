import * as React from "react"

import { cn } from "@/lib/utils"

function Input({ className, type, ...props }: React.ComponentProps<"input">) {
  return (
    <input
      type={type}
      data-slot="input"
      // Suppress hydration warnings caused by browser extensions (e.g., Dashlane)
      // adding attributes like data-dashlane-rid to input elements
      suppressHydrationWarning
      className={cn(
        "h-9 w-full min-w-0 rounded-md border border-border bg-surface/70 px-3 py-1 text-base text-text shadow-xs transition-all duration-200 ease-in-out outline-none placeholder:text-text-muted selection:bg-primary/80 selection:text-primary-foreground focus-visible:border-focus focus-visible:ring-2 focus-visible:ring-focus/30 file:inline-flex file:h-7 file:items-center file:justify-center file:rounded-sm file:border-0 file:bg-primary/15 file:px-2.5 file:text-xs file:font-medium file:uppercase file:text-primary disabled:pointer-events-none disabled:cursor-not-allowed disabled:opacity-35 md:text-sm",
        "aria-invalid:border-destructive aria-invalid:ring-2 aria-invalid:ring-destructive/25",
        className
      )}
      {...props}
    />
  )
}

export { Input }
