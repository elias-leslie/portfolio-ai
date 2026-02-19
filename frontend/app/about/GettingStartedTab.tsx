'use client'

import { ArrowRight, CheckCircle2 } from 'lucide-react'
import { motion } from 'motion/react'
import { cn } from '@/lib/utils'
import { quickStartPages, setupChecklist } from './_data'

function QuickStartLinks() {
  return (
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
  )
}

function SetupChecklist() {
  return (
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
      <div className="p-4 rounded-lg bg-primary/5 border border-primary/20">
        <p className="text-sm text-text-muted">
          <span className="font-medium text-primary">Tip:</span> Start by
          adding your portfolio positions, then explore the Watchlist to see
          AI-powered signals in action.
        </p>
      </div>
    </div>
  )
}

export function GettingStartedTab() {
  return (
    <div className="grid lg:grid-cols-2 gap-8">
      <QuickStartLinks />
      <SetupChecklist />
    </div>
  )
}
