import { redirect } from 'next/navigation'
import { CapabilitiesPageClient } from './CapabilitiesPageClient'
import { ADVANCED_PRODUCT_MODE_ENABLED } from '@/lib/product-routes'

export default function CapabilitiesPage() {
  if (!ADVANCED_PRODUCT_MODE_ENABLED) {
    redirect('/')
  }

  return <CapabilitiesPageClient />
}
