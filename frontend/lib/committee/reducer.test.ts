import { describe, expect, it } from 'vitest'
import snapshot from './__fixtures__/run-0bd2b5fc.json'
import type { CommitteeEvent } from './events'
import { INITIAL_COMMITTEE_STATE, reduceCommitteeEvents } from './reducer'

// Real event log from production run NVDA → hold (run id 0bd2b5fc-…).
// The reducer must populate every display field from the raw snake_case
// events, exactly as both the SSE stream and the snapshot endpoint emit
// them. A camelCase mutation anywhere in the path would zero out these
// reads, which is the bug this fixture pins down.

const events = (snapshot as { events: CommitteeEvent[] }).events

describe('reduceCommitteeEvents on the run-0bd2b5fc transcript', () => {
  const final = reduceCommitteeEvents(INITIAL_COMMITTEE_STATE, events)

  it('completes the run and captures symbol + graph version', () => {
    expect(final.status).toBe('complete')
    expect(final.symbol).toBe('NVDA')
    expect(final.graph_version).toBe('committee.v0.3.1')
  })

  it('captures all 4 analyst outputs with content + score + evidence', () => {
    const analysts = Object.values(final.agents).filter(
      (a) => a.role === 'analyst',
    )
    expect(analysts).toHaveLength(4)
    const fundamentals = final.agents['fundamentals-v1']
    expect(fundamentals).toBeDefined()
    expect(fundamentals.content_md.length).toBeGreaterThan(50)
    expect(fundamentals.score).toBeCloseTo(0.15)
    expect(fundamentals.evidence.length).toBeGreaterThan(0)
    expect(fundamentals.evidence[0]).toMatchObject({
      claim: expect.any(String),
      side: expect.stringMatching(/bull|bear|neutral/),
    })
    expect(fundamentals.tokens).toBeGreaterThan(0)
  })

  it('captures bull/bear debate rounds with argument content', () => {
    expect(final.debate_rounds.length).toBeGreaterThanOrEqual(3)
    const round = final.debate_rounds[0]
    expect(round.bull).toBeDefined()
    expect(round.bull?.content_md.length).toBeGreaterThan(50)
    expect(round.bear).toBeDefined()
    expect(round.bear?.content_md.length).toBeGreaterThan(50)
    expect(round.completed).toBe(true)
    expect(round.bull_score).not.toBeNull()
    expect(round.bear_score).not.toBeNull()
  })

  it('records IPS checks with passed/severity/value/threshold', () => {
    expect(final.ips_checks).toHaveLength(4)
    const names = final.ips_checks.map((c) => c.name).sort()
    expect(names).toEqual([
      'concentration',
      'sector_exposure',
      'tax_bill',
      'wash_sale',
    ])
    const concentration = final.ips_checks.find(
      (c) => c.name === 'concentration',
    )
    expect(concentration?.passed).toBe(true)
    expect(concentration?.severity).toBe('info')
    expect(concentration?.value).toBeCloseTo(0.04)
    expect(concentration?.threshold).toBeCloseTo(0.25)
  })

  it('records 3 risk votes with narrative and vote shape', () => {
    expect(final.risk_votes).toHaveLength(3)
    const slugs = final.risk_votes.map((v) => v.agent_slug).sort()
    expect(slugs).toEqual([
      'risk-aggressive-v1',
      'risk-conservative-v1',
      'risk-neutral-v1',
    ])
    for (const vote of final.risk_votes) {
      expect(vote.narrative_md.length).toBeGreaterThan(20)
      expect(['approve', 'downgrade', 'reject']).toContain(vote.vote)
    }
  })

  it('captures the PM decision with qty_pct, confidence, rationale', () => {
    expect(final.decision).not.toBeNull()
    expect(final.decision?.action).toBe('hold')
    expect(final.decision?.qty_pct).toBe(0)
    expect(final.decision?.confidence).toBeCloseTo(0.72)
    expect(final.decision?.horizon).toBe('1-3 months')
    expect(final.decision?.rationale_md?.length).toBeGreaterThan(100)
    expect(final.decision?.signers).toContain('risk-aggressive-v1')
  })

  it('captures tokens_total and elapsed_ms from run.complete', () => {
    expect(final.kpi.tokens_total).toBe(64255)
    expect(final.kpi.elapsed_ms).toBeGreaterThan(0)
  })
})
