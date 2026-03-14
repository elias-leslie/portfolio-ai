import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { SentimentTooltip, normalizeNewsSentiment } from '../SentimentTooltip'

describe('normalizeNewsSentiment', () => {
  it('maps -1 to 0', () => {
    expect(normalizeNewsSentiment(-1)).toBe(0)
  })

  it('maps 0 to 50', () => {
    expect(normalizeNewsSentiment(0)).toBe(50)
  })

  it('maps +1 to 100', () => {
    expect(normalizeNewsSentiment(1)).toBe(100)
  })

  it('maps 0.5 to 75', () => {
    expect(normalizeNewsSentiment(0.5)).toBe(75)
  })
})

describe('SentimentTooltip', () => {
  it('returns nothing when inactive', () => {
    const { container } = render(
      <SentimentTooltip active={false} payload={[]} label="2026-03-14" />,
    )

    expect(container.innerHTML).toBe('')
  })

  it('shows fear and greed score when present', () => {
    render(
      <SentimentTooltip
        active
        label="2026-03-14"
        payload={[
          {
            value: 42,
            dataKey: 'score',
            payload: { label: 'Fear' },
          },
        ]}
      />,
    )

    expect(screen.getByText('42 (Fear)')).toBeInTheDocument()
  })

  it('shows news sentiment as a percentage', () => {
    render(
      <SentimentTooltip
        active
        label="2026-03-14"
        payload={[
          {
            value: 75,
            dataKey: 'newsSentiment',
            payload: { newsRaw: 0.35 },
          },
        ]}
      />,
    )

    expect(screen.getByText(/\+35%/)).toBeInTheDocument()
  })

  it('shows put/call ratio with two decimal places', () => {
    render(
      <SentimentTooltip
        active
        label="2026-03-14"
        payload={[
          {
            value: 50,
            dataKey: 'pcRatioScaled',
            payload: { pcRatioRaw: 0.87 },
          },
        ]}
      />,
    )

    expect(screen.getByText('0.87')).toBeInTheDocument()
  })
})
