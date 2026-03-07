import { redirect } from 'next/navigation'
import { RecommendationsPageClient } from './RecommendationsPageClient'
import { ADVANCED_PRODUCT_MODE_ENABLED } from '@/lib/product-routes'

export default function RecommendationsPage() {
  if (!ADVANCED_PRODUCT_MODE_ENABLED) {
    redirect('/')
  }

  return <RecommendationsPageClient />
}
