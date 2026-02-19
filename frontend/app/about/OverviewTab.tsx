'use client'

import { ArrowRight, Layers } from 'lucide-react'
import { motion } from 'motion/react'
import { cn } from '@/lib/utils'
import { coreConcepts } from './_data'

function ArchitectureDiagram() {
  const stages = ['Frontend', 'API', 'Workers', 'Database']
  return (
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
          {stages.map((stage, i) => (
            <span key={stage} className="flex items-center gap-2">
              <span className="px-2 py-1 rounded bg-surface-muted">{stage}</span>
              {i < stages.length - 1 && <ArrowRight className="w-3 h-3" />}
            </span>
          ))}
        </div>
      </div>
    </div>
  )
}

export function OverviewTab() {
  return (
    <div className="space-y-12">
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

      <ArchitectureDiagram />
    </div>
  )
}
