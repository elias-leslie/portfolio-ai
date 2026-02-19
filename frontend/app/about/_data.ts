import {
  Activity,
  BarChart3,
  Bot,
  Brain,
  Briefcase,
  Clock,
  Database,
  Eye,
  Gauge,
  Layers,
  LineChart,
  Shield,
  Target,
  TrendingUp,
  Zap,
} from 'lucide-react'

export const tabs = [
  { id: 'overview', label: 'Overview' },
  { id: 'how-it-works', label: 'How It Works' },
  { id: 'getting-started', label: 'Getting Started' },
  { id: 'features', label: 'Features' },
] as const

export type TabId = (typeof tabs)[number]['id']

export const trustIndicators = [
  {
    icon: Activity,
    label: 'Real-time Analytics',
    description: 'Live portfolio metrics',
  },
  {
    icon: Bot,
    label: 'AI Agents',
    description: 'Claude-powered insights',
  },
  {
    icon: Database,
    label: 'Multi-Source Data',
    description: '6 providers with failover',
  },
]

export const coreConcepts = [
  {
    icon: LineChart,
    title: 'Portfolio Analytics',
    description:
      'Track beta, volatility, concentration, and sector exposure across all your accounts in real-time.',
    color: 'text-primary',
    bgColor: 'bg-primary/10',
  },
  {
    icon: Brain,
    title: 'AI Agents',
    description:
      'Discovery Agent scans market opportunities. Portfolio Analyzer provides personalized insights based on your holdings.',
    color: 'text-accent',
    bgColor: 'bg-accent/10',
  },
  {
    icon: Eye,
    title: 'Watchlist Intelligence',
    description:
      'Signal classification (BUY/HOLD/AVOID), trading style recommendations, and narrative insights for every ticker.',
    color: 'text-gain',
    bgColor: 'bg-gain/10',
  },
]

export const workflowSteps = [
  {
    step: 1,
    title: 'Add Your Holdings',
    description:
      'Import your portfolio positions from multiple accounts (IRA, Taxable, 401k, Roth, HSA).',
    icon: Briefcase,
  },
  {
    step: 2,
    title: 'AI Analysis',
    description:
      'Our agents analyze your portfolio, market conditions, and news to generate insights.',
    icon: Brain,
  },
  {
    step: 3,
    title: 'Get Signals',
    description:
      'Receive actionable signals with plain-language explanations - no jargon, just clarity.',
    icon: Target,
  },
  {
    step: 4,
    title: 'Take Action',
    description:
      'Paper trade to test ideas, backtest strategies, or execute with confidence.',
    icon: TrendingUp,
  },
]

export const quickStartPages = [
  { href: '/portfolio', label: 'Portfolio', description: 'Manage positions' },
  { href: '/watchlist', label: 'Watchlist', description: 'Track signals' },
  { href: '/trading', label: 'Trading', description: 'Paper trade' },
  {
    href: '/settings',
    label: 'Settings',
    description: 'Configure preferences',
  },
]

export const setupChecklist = [
  { label: 'Add your first portfolio account', done: false },
  { label: 'Import or add positions', done: false },
  { label: 'Add tickers to your watchlist', done: false },
  { label: 'Set your risk tolerance in Settings', done: false },
  { label: 'Explore AI-generated ideas', done: false },
]

export const features = [
  {
    icon: Gauge,
    title: 'Fear & Greed Index',
    description:
      'Market sentiment combining VIX, momentum, RSI, and credit spreads into a single 0-100 score.',
  },
  {
    icon: BarChart3,
    title: 'Backtesting',
    description:
      'Test your strategies against historical data before committing real capital.',
  },
  {
    icon: Shield,
    title: 'Paper Trading',
    description:
      'Practice trading with virtual funds to validate ideas without risk.',
  },
  {
    icon: Layers,
    title: 'Multi-Source Data',
    description:
      'YFinance, Polygon, TwelveData, FMP, Finnhub, AlphaVantage with automatic failover.',
  },
  {
    icon: Clock,
    title: 'Scheduled Refresh',
    description:
      'Automated data updates via Celery workers keep your insights fresh.',
  },
  {
    icon: Zap,
    title: 'Narrative Intelligence',
    description:
      'Plain-language trading recommendations with entry, stop, and target levels.',
  },
]
