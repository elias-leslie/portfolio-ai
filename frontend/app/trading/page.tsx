import { redirect } from 'next/navigation'
import { TradingPageClient } from './TradingPageClient'
import { ADVANCED_PRODUCT_MODE_ENABLED } from '@/lib/product-routes'

export default function TradingPage() {
  if (!ADVANCED_PRODUCT_MODE_ENABLED) {
    redirect('/')
  }

  return <TradingPageClient />
}
