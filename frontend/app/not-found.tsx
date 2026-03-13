import { ArrowLeft, MapPinOff } from 'lucide-react'
import Link from 'next/link'
import { Button } from '@/components/ui/button'

export default function NotFound() {
  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center gap-6 p-8">
      <div className="rounded-full bg-surface-muted p-4">
        <MapPinOff className="h-8 w-8 text-text-muted" />
      </div>
      <div className="space-y-2 text-center">
        <h2 className="text-xl font-semibold text-text">Page not found</h2>
        <p className="max-w-md text-sm text-text-muted leading-relaxed">
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
