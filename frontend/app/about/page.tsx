'use client'

import {
  Activity,
  ArrowRight,
  BarChart3,
  Bot,
  Brain,
  Briefcase,
  CheckCircle2,
  ChevronRight,
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
import { AnimatePresence, motion } from 'motion/react'
import { useState } from 'react'
import { PageContainer } from '@/components/shared/PageContainer'
import { cn } from '@/lib/utils'

// Tab configuration
const tabs = [
  { id: 'overview', label: 'Overview' },
  { id: 'how-it-works', label: 'How It Works' },
  { id: 'getting-started', label: 'Getting Started' },
  { id: 'features', label: 'Features' },
] as const

type TabId = (typeof tabs)[number]['id']

// Trust indicators for hero
const trustIndicators = [
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

// Core concepts for overview
const coreConcepts = [
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

// Workflow steps
const workflowSteps = [
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

// Quick start pages
const quickStartPages = [
  { href: '/portfolio', label: 'Portfolio', description: 'Manage positions' },
  { href: '/watchlist', label: 'Watchlist', description: 'Track signals' },
  { href: '/trading', label: 'Trading', description: 'Paper trade' },
  {
    href: '/settings',
    label: 'Settings',
    description: 'Configure preferences',
  },
]

// Setup checklist
const setupChecklist = [
  { label: 'Add your first portfolio account', done: false },
  { label: 'Import or add positions', done: false },
  { label: 'Add tickers to your watchlist', done: false },
  { label: 'Set your risk tolerance in Settings', done: false },
  { label: 'Explore AI-generated ideas', done: false },
]

// Features grid
const features = [
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

// Animation variants
const fadeInUp = {
  initial: { opacity: 0, y: 20 },
  animate: { opacity: 1, y: 0 },
  exit: { opacity: 0, y: -10 },
}

const stagger = {
  animate: {
    transition: {
      staggerChildren: 0.08,
    },
  },
}

export default function AboutPage() {
  const [activeTab, setActiveTab] = useState<TabId>('overview')

  return (
    <PageContainer className="py-12 space-y-12">
      {/* Hero Section */}
      <motion.section
        initial="initial"
        animate="animate"
        variants={stagger}
        className="text-center space-y-8"
      >
        <motion.div variants={fadeInUp} className="space-y-4">
          <p className="text-xs font-semibold uppercase tracking-widest text-primary">
            Welcome to Portfolio AI
          </p>
          <h1 className="text-4xl sm:text-5xl lg:text-6xl font-bold tracking-tight">
            <span className="bg-gradient-to-r from-primary via-accent to-primary bg-clip-text text-transparent">
              AI-Led Investment
            </span>
            <br />
            <span className="text-text">Intelligence</span>
          </h1>
          <p className="max-w-2xl mx-auto text-lg text-text-muted">
            Combine portfolio analytics with autonomous agent-driven market
            insights. Real-time analysis, plain-language signals, and actionable
            recommendations.
          </p>
        </motion.div>

        {/* Trust Indicators */}
        <motion.div
          variants={fadeInUp}
          className="flex flex-wrap justify-center gap-6 pt-4"
        >
          {trustIndicators.map((item) => (
            <div
              key={item.label}
              className="flex items-center gap-3 px-4 py-2 rounded-full bg-surface-muted/50 border border-border/30"
            >
              <item.icon className="w-5 h-5 text-primary" />
              <div className="text-left">
                <p className="text-sm font-medium text-text">{item.label}</p>
                <p className="text-xs text-text-muted">{item.description}</p>
              </div>
            </div>
          ))}
        </motion.div>
      </motion.section>

      {/* Tabbed Interface */}
      <section className="space-y-8">
        {/* Tab List */}
        <div className="flex justify-center">
          <div className="inline-flex items-center gap-1 p-1 rounded-full bg-surface-muted/50 border border-border/30">
            {tabs.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={cn(
                  'px-4 py-2 text-sm font-medium rounded-full transition-all duration-200',
                  activeTab === tab.id
                    ? 'bg-primary text-primary-foreground shadow-md'
                    : 'text-text-muted hover:text-text hover:bg-surface',
                )}
              >
                {tab.label}
              </button>
            ))}
          </div>
        </div>

        {/* Tab Content */}
        <AnimatePresence mode="wait">
          <motion.div
            key={activeTab}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            transition={{ duration: 0.2 }}
          >
            {activeTab === 'overview' && <OverviewTab />}
            {activeTab === 'how-it-works' && <HowItWorksTab />}
            {activeTab === 'getting-started' && <GettingStartedTab />}
            {activeTab === 'features' && <FeaturesTab />}
          </motion.div>
        </AnimatePresence>
      </section>
    </PageContainer>
  )
}

// Overview Tab
function OverviewTab() {
  return (
    <div className="space-y-12">
      {/* What is Portfolio AI */}
      <div className="max-w-3xl mx-auto text-center space-y-4">
        <h2 className="text-2xl font-semibold text-text">
          What is Portfolio AI?
        </h2>
        <p className="text-text-muted leading-relaxed">
          Portfolio AI is an AI-led investment intelligence platform that
          combines portfolio analytics with autonomous agent-driven market
          insights. The system analyzes your holdings, monitors market
          conditions, and generates actionable investment ideas using Claude AI
          - translating complex technical data into plain-language
          recommendations.
        </p>
      </div>

      {/* Core Concepts */}
      <div className="grid md:grid-cols-3 gap-6">
        {coreConcepts.map((concept, index) => (
          <motion.div
            key={concept.title}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: index * 0.1 }}
            className="group relative p-6 rounded-xl bg-surface-elev border border-border/50 hover:border-border transition-all duration-200"
          >
            <div
              className={cn(
                'w-12 h-12 rounded-lg flex items-center justify-center mb-4',
                concept.bgColor,
              )}
            >
              <concept.icon className={cn('w-6 h-6', concept.color)} />
            </div>
            <h3 className="text-lg font-semibold text-text mb-2">
              {concept.title}
            </h3>
            <p className="text-sm text-text-muted leading-relaxed">
              {concept.description}
            </p>
          </motion.div>
        ))}
      </div>

      {/* Architecture Placeholder */}
      <div className="rounded-xl border border-border/50 bg-surface-muted/30 p-8">
        <div className="flex flex-col items-center justify-center text-center space-y-4 py-8">
          <Layers className="w-12 h-12 text-text-muted/50" />
          <div>
            <p className="text-sm font-medium text-text-muted">
              Architecture Overview
            </p>
            <p className="text-xs text-text-muted/70 mt-1">
              Next.js + FastAPI + PostgreSQL + Celery + Claude AI
            </p>
          </div>
          <div className="flex items-center gap-2 text-xs text-text-muted/50">
            <span className="px-2 py-1 rounded bg-surface-muted">Frontend</span>
            <ArrowRight className="w-3 h-3" />
            <span className="px-2 py-1 rounded bg-surface-muted">API</span>
            <ArrowRight className="w-3 h-3" />
            <span className="px-2 py-1 rounded bg-surface-muted">Workers</span>
            <ArrowRight className="w-3 h-3" />
            <span className="px-2 py-1 rounded bg-surface-muted">Database</span>
          </div>
        </div>
      </div>
    </div>
  )
}

// How It Works Tab
function HowItWorksTab() {
  return (
    <div className="space-y-12">
      {/* Workflow Steps */}
      <div className="max-w-4xl mx-auto">
        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-6">
          {workflowSteps.map((step, index) => (
            <motion.div
              key={step.step}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: index * 0.1 }}
              className="relative"
            >
              {/* Connector line */}
              {index < workflowSteps.length - 1 && (
                <div className="hidden lg:block absolute top-8 left-full w-full h-px bg-gradient-to-r from-border to-transparent z-0" />
              )}

              <div className="relative p-6 rounded-xl bg-surface-elev border border-border/50 h-full">
                {/* Step number */}
                <div className="absolute -top-3 -left-3 w-8 h-8 rounded-full bg-primary text-primary-foreground text-sm font-bold flex items-center justify-center shadow-lg">
                  {step.step}
                </div>

                <div className="pt-2">
                  <step.icon className="w-8 h-8 text-accent mb-3" />
                  <h3 className="text-base font-semibold text-text mb-2">
                    {step.title}
                  </h3>
                  <p className="text-sm text-text-muted leading-relaxed">
                    {step.description}
                  </p>
                </div>
              </div>
            </motion.div>
          ))}
        </div>
      </div>

      {/* Signal Flow Visualization */}
      <div className="max-w-3xl mx-auto rounded-xl border border-border/50 bg-surface-muted/30 p-8">
        <h3 className="text-lg font-semibold text-text text-center mb-6">
          Signal Classification Flow
        </h3>
        <div className="flex flex-wrap items-center justify-center gap-4">
          <div className="px-4 py-2 rounded-lg bg-surface-elev border border-border/50">
            <p className="text-xs text-text-muted mb-1">Technical Data</p>
            <p className="text-sm font-mono text-text">RSI, MACD, EMA</p>
          </div>
          <ChevronRight className="w-5 h-5 text-text-muted" />
          <div className="px-4 py-2 rounded-lg bg-surface-elev border border-border/50">
            <p className="text-xs text-text-muted mb-1">Fundamentals</p>
            <p className="text-sm font-mono text-text">P/E, Growth, Debt</p>
          </div>
          <ChevronRight className="w-5 h-5 text-text-muted" />
          <div className="px-4 py-2 rounded-lg bg-surface-elev border border-border/50">
            <p className="text-xs text-text-muted mb-1">AI Classification</p>
            <p className="text-sm font-mono text-text">Signal + Narrative</p>
          </div>
          <ChevronRight className="w-5 h-5 text-text-muted" />
          <div className="flex gap-2">
            <span className="px-3 py-1 rounded-full bg-gain/20 text-gain text-sm font-medium">
              BUY
            </span>
            <span className="px-3 py-1 rounded-full bg-warning/20 text-warning text-sm font-medium">
              HOLD
            </span>
            <span className="px-3 py-1 rounded-full bg-loss/20 text-loss text-sm font-medium">
              AVOID
            </span>
          </div>
        </div>
      </div>
    </div>
  )
}

// Getting Started Tab
function GettingStartedTab() {
  return (
    <div className="grid lg:grid-cols-2 gap-8">
      {/* Quick Start */}
      <div className="space-y-6">
        <h2 className="text-xl font-semibold text-text">Quick Start</h2>

        <div className="space-y-4">
          {quickStartPages.map((page, index) => (
            <motion.a
              key={page.href}
              href={page.href}
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: index * 0.05 }}
              className="group flex items-center justify-between p-4 rounded-xl bg-surface-elev border border-border/50 hover:border-primary/50 transition-all duration-200"
            >
              <div>
                <p className="font-medium text-text group-hover:text-primary transition-colors">
                  {page.label}
                </p>
                <p className="text-sm text-text-muted">{page.description}</p>
              </div>
              <ArrowRight className="w-5 h-5 text-text-muted group-hover:text-primary group-hover:translate-x-1 transition-all" />
            </motion.a>
          ))}
        </div>
      </div>

      {/* Setup Checklist */}
      <div className="space-y-6">
        <h2 className="text-xl font-semibold text-text">Setup Checklist</h2>

        <div className="p-6 rounded-xl bg-surface-elev border border-border/50">
          <div className="space-y-4">
            {setupChecklist.map((item, index) => (
              <motion.div
                key={item.label}
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: index * 0.05 }}
                className="flex items-start gap-3"
              >
                <div
                  className={cn(
                    'w-5 h-5 rounded-full border-2 flex items-center justify-center flex-shrink-0 mt-0.5',
                    item.done
                      ? 'border-gain bg-gain/20'
                      : 'border-text-muted/30',
                  )}
                >
                  {item.done && <CheckCircle2 className="w-3 h-3 text-gain" />}
                </div>
                <p
                  className={cn(
                    'text-sm',
                    item.done ? 'text-text-muted line-through' : 'text-text',
                  )}
                >
                  {item.label}
                </p>
              </motion.div>
            ))}
          </div>
        </div>

        {/* Tip Box */}
        <div className="p-4 rounded-lg bg-primary/5 border border-primary/20">
          <p className="text-sm text-text-muted">
            <span className="font-medium text-primary">Tip:</span> Start by
            adding your portfolio positions, then explore the Watchlist to see
            AI-powered signals in action.
          </p>
        </div>
      </div>
    </div>
  )
}

// Features Tab
function FeaturesTab() {
  return (
    <div className="space-y-12">
      {/* Feature Grid */}
      <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-6">
        {features.map((feature, index) => (
          <motion.div
            key={feature.title}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: index * 0.08 }}
            className="group p-6 rounded-xl bg-surface-elev border border-border/50 hover:border-accent/30 transition-all duration-200"
          >
            <feature.icon className="w-8 h-8 text-accent mb-4 group-hover:scale-110 transition-transform" />
            <h3 className="text-base font-semibold text-text mb-2">
              {feature.title}
            </h3>
            <p className="text-sm text-text-muted leading-relaxed">
              {feature.description}
            </p>
          </motion.div>
        ))}
      </div>

      {/* Screenshot Placeholders */}
      <div className="grid md:grid-cols-2 gap-6">
        <div className="rounded-xl border border-border/50 bg-surface-muted/30 aspect-video flex items-center justify-center">
          <div className="text-center space-y-2">
            <Eye className="w-10 h-10 text-text-muted/50 mx-auto" />
            <p className="text-sm text-text-muted">Watchlist Dashboard</p>
            <p className="text-xs text-text-muted/70">Screenshot placeholder</p>
          </div>
        </div>
        <div className="rounded-xl border border-border/50 bg-surface-muted/30 aspect-video flex items-center justify-center">
          <div className="text-center space-y-2">
            <BarChart3 className="w-10 h-10 text-text-muted/50 mx-auto" />
            <p className="text-sm text-text-muted">Portfolio Analytics</p>
            <p className="text-xs text-text-muted/70">Screenshot placeholder</p>
          </div>
        </div>
      </div>
    </div>
  )
}
