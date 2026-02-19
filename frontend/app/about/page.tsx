'use client'

import { AnimatePresence, motion } from 'motion/react'
import { useState } from 'react'
import { PageContainer } from '@/components/shared/PageContainer'
import { cn } from '@/lib/utils'
import { fadeInUp, stagger } from './_animations'
import { tabs, trustIndicators, type TabId } from './_data'
import { FeaturesTab } from './FeaturesTab'
import { GettingStartedTab } from './GettingStartedTab'
import { HowItWorksTab } from './HowItWorksTab'
import { OverviewTab } from './OverviewTab'

function HeroSection() {
  return (
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
  )
}

interface TabNavProps {
  activeTab: TabId
  onTabChange: (id: TabId) => void
}

function TabNav({ activeTab, onTabChange }: TabNavProps) {
  return (
    <div className="flex justify-center">
      <div className="inline-flex items-center gap-1 p-1 rounded-full bg-surface-muted/50 border border-border/30">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => onTabChange(tab.id)}
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
  )
}

function TabContent({ activeTab }: { activeTab: TabId }) {
  return (
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
  )
}

export default function AboutPage() {
  const [activeTab, setActiveTab] = useState<TabId>('overview')

  return (
    <PageContainer className="py-12 space-y-12">
      <HeroSection />
      <section className="space-y-8">
        <TabNav activeTab={activeTab} onTabChange={setActiveTab} />
        <TabContent activeTab={activeTab} />
      </section>
    </PageContainer>
  )
}
