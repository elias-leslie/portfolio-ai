import { redirect } from 'next/navigation'

export default function WatchlistPage() {
  redirect('/portfolio?tab=symbols')
}
