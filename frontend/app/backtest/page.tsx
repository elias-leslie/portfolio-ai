import { redirect } from 'next/navigation'
import { BacktestPageClient } from './BacktestPageClient'
import { ADVANCED_PRODUCT_MODE_ENABLED } from '@/lib/product-routes'

export default function BacktestPage() {
  if (!ADVANCED_PRODUCT_MODE_ENABLED) {
    redirect('/')
  }

  return <BacktestPageClient />
}
