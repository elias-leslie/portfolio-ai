import { redirect } from 'next/navigation'
import { StrategiesPageClient } from './StrategiesPageClient'
import { ADVANCED_PRODUCT_MODE_ENABLED } from '@/lib/product-routes'

export default function StrategiesPage() {
  if (!ADVANCED_PRODUCT_MODE_ENABLED) {
    redirect('/')
  }

  return <StrategiesPageClient />
}
