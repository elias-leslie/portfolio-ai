import { describe, expect, it } from 'vitest'
import { buildTodayGate } from '../ScannerMetricBadges'

describe('buildTodayGate', () => {
  it('uses split macro and tape scores for a selective tape-driven gate', () => {
    const gate = buildTodayGate({
      overallRead: 'selective',
      primaryDriver: 'tape',
      deploymentScore: 63,
      macroStressScore: 37,
      tapePressureScore: 62,
      overallCautionScore: 62,
      coverage: 1,
    })

    expect(gate).toEqual({
      label: 'Selective',
      tone: 'caution',
      detail:
        'Macro 63, tape 62. Tape is the main caution; highest-conviction buys only.',
    })
  })

  it('keeps defensive styling only for a defensive overall read', () => {
    const selectiveGate = buildTodayGate({
      overallRead: 'selective',
      primaryDriver: 'tape',
      deploymentScore: 82,
      tapePressureScore: 62,
      coverage: 1,
    })
    const defensiveGate = buildTodayGate({
      overallRead: 'defensive',
      primaryDriver: 'both',
      deploymentScore: 30,
      tapePressureScore: 68,
      coverage: 1,
    })

    expect(selectiveGate?.tone).toBe('caution')
    expect(defensiveGate?.tone).toBe('defensive')
  })
})
