'use client'

import { BarChart3, Eye } from 'lucide-react'
import { motion } from 'motion/react'
import { features } from './_data'

function ScreenshotPlaceholders() {
  const placeholders = [
    { icon: Eye, label: 'Watchlist Dashboard' },
    { icon: BarChart3, label: 'Portfolio Analytics' },
  ]
  return (
    <div className="grid md:grid-cols-2 gap-6">
      {placeholders.map(({ icon: Icon, label }) => (
        <div
          key={label}
          className="rounded-xl border border-border/50 bg-surface-muted/30 aspect-video flex items-center justify-center"
        >
          <div className="text-center space-y-2">
            <Icon className="w-10 h-10 text-text-muted/50 mx-auto" />
            <p className="text-sm text-text-muted">{label}</p>
            <p className="text-xs text-text-muted/70">Screenshot placeholder</p>
          </div>
        </div>
      ))}
    </div>
  )
}

export function FeaturesTab() {
  return (
    <div className="space-y-12">
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
      <ScreenshotPlaceholders />
    </div>
  )
}
