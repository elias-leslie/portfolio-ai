import { ArrowLeft, MapPinOff } from 'lucide-react'
import Link from 'next/link'
import { Button } from '@/components/ui/button'

export default function NotFound() {
  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center gap-8 p-8">
      <div className="relative">
        <div className="absolute -inset-6 rounded-full bg-primary/5 blur-2xl" />
        <div className="relative rounded-full border border-border/40 bg-surface-muted/50 p-5 shadow-lg">
          <MapPinOff className="h-10 w-10 text-text-muted" />
        </div>
      </div>
      <div className="space-y-3 text-center">
        <p className="text-xs font-semibold uppercase tracking-widest text-text-muted">
          404
        </p>
        <h2 className="font-display italic text-3xl text-text">
          Page not found
        </h2>
        <p className="max-w-md text-sm leading-relaxed text-text-muted">
          The page you are looking for does not exist or may have been moved.
        </p>
      </div>
      <Button asChild>
        <Link href="/">
          <ArrowLeft className="mr-2 h-4 w-4" />
          Back to Dashboard
        </Link>
      </Button>
    </div>
  )
}
