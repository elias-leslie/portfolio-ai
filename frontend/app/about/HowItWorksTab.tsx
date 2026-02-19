'use client'

import { ChevronRight } from 'lucide-react'
import { motion } from 'motion/react'
import { workflowSteps } from './_data'

function SignalClassificationFlow() {
  const inputs = [
    { label: 'Technical Data', value: 'RSI, MACD, EMA' },
    { label: 'Fundamentals', value: 'P/E, Growth, Debt' },
    { label: 'AI Classification', value: 'Signal + Narrative' },
  ]
  const signals = [
    { label: 'BUY', className: 'bg-gain/20 text-gain' },
    { label: 'HOLD', className: 'bg-warning/20 text-warning' },
    { label: 'AVOID', className: 'bg-loss/20 text-loss' },
  ]

  return (
    <div className="max-w-3xl mx-auto rounded-xl border border-border/50 bg-surface-muted/30 p-8">
      <h3 className="text-lg font-semibold text-text text-center mb-6">
        Signal Classification Flow
      </h3>
      <div className="flex flex-wrap items-center justify-center gap-4">
        {inputs.map((item, i) => (
          <span key={item.label} className="flex items-center gap-4">
            <div className="px-4 py-2 rounded-lg bg-surface-elev border border-border/50">
              <p className="text-xs text-text-muted mb-1">{item.label}</p>
              <p className="text-sm font-mono text-text">{item.value}</p>
            </div>
            {i < inputs.length - 1 && (
              <ChevronRight className="w-5 h-5 text-text-muted" />
            )}
          </span>
        ))}
        <ChevronRight className="w-5 h-5 text-text-muted" />
        <div className="flex gap-2">
          {signals.map((signal) => (
            <span
              key={signal.label}
              className={`px-3 py-1 rounded-full text-sm font-medium ${signal.className}`}
            >
              {signal.label}
            </span>
          ))}
        </div>
      </div>
    </div>
  )
}

export function HowItWorksTab() {
  return (
    <div className="space-y-12">
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
              {index < workflowSteps.length - 1 && (
                <div className="hidden lg:block absolute top-8 left-full w-full h-px bg-gradient-to-r from-border to-transparent z-0" />
              )}
              <div className="relative p-6 rounded-xl bg-surface-elev border border-border/50 h-full">
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
      <SignalClassificationFlow />
    </div>
  )
}
