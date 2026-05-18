import { cn } from '@/lib/utils'

export function DeterministicBadge({
  className,
  label = 'DETERMINISTIC · back-testable',
}: {
  className?: string
  label?: string
}) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.16em]',
        'border border-[#00f5ff]/40 bg-[#00f5ff]/10 text-[#00f5ff]',
        className,
      )}
      title="Deterministic signal — fixed rules, reproducible, back-testable."
    >
      <span
        aria-hidden="true"
        className="inline-block h-1.5 w-1.5 rounded-full bg-[#00f5ff] shadow-[0_0_6px_#00f5ff]"
      />
      {label}
    </span>
  )
}

export function NonDeterministicBadge({
  className,
  costPerRun = '$0.50',
}: {
  className?: string
  costPerRun?: string
}) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.16em]',
        'border border-[#a855f7]/40 bg-[#a855f7]/10 text-[#a855f7]',
        className,
      )}
      title="AI judgment — non-deterministic, costs tokens per run, not back-testable."
    >
      <span
        aria-hidden="true"
        className="inline-block h-1.5 w-1.5 rounded-full bg-[#a855f7] shadow-[0_0_6px_#a855f7]"
      />
      AI · non-deterministic · ~{costPerRun}/run
    </span>
  )
}
