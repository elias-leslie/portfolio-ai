import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it } from 'vitest'
import { WorkspaceTabs } from '../WorkspaceTabs'

describe('WorkspaceTabs', () => {
  beforeEach(() => {
    window.history.replaceState({}, '', '/money')
  })

  it('uses the tab query parameter when it matches an available tab', () => {
    window.history.replaceState({}, '', '/money?tab=planning')

    render(
      <WorkspaceTabs
        defaultValue="operate"
        tabs={[
          {
            value: 'operate',
            label: 'Operate',
            description: 'Run the day-to-day queue.',
            content: <div>Operate Content</div>,
          },
          {
            value: 'planning',
            label: 'Planning',
            description: 'Review the longer-term plan.',
            content: <div>Planning Content</div>,
          },
        ]}
      />,
    )

    expect(screen.getByText('Planning Content')).toBeInTheDocument()
    expect(screen.getByText('Review the longer-term plan.')).toBeInTheDocument()
  })

  it('updates the query string while preserving unrelated parameters', async () => {
    const user = userEvent.setup()
    window.history.replaceState({}, '', '/money?symbol=VTI')

    render(
      <WorkspaceTabs
        defaultValue="operate"
        tabs={[
          {
            value: 'operate',
            label: 'Operate',
            description: 'Run the day-to-day queue.',
            content: <div>Operate Content</div>,
          },
          {
            value: 'planning',
            label: 'Planning',
            description: 'Review the longer-term plan.',
            content: <div>Planning Content</div>,
          },
        ]}
      />,
    )

    await user.click(screen.getByRole('button', { name: 'Planning' }))

    expect(window.location.pathname).toBe('/money')
    expect(window.location.search).toBe('?symbol=VTI&tab=planning')
  })

  it('removes the tab query parameter when returning to the default tab', async () => {
    const user = userEvent.setup()
    window.history.replaceState({}, '', '/money?symbol=VTI&tab=planning')

    render(
      <WorkspaceTabs
        defaultValue="operate"
        tabs={[
          {
            value: 'operate',
            label: 'Operate',
            description: 'Run the day-to-day queue.',
            content: <div>Operate Content</div>,
          },
          {
            value: 'planning',
            label: 'Planning',
            description: 'Review the longer-term plan.',
            content: <div>Planning Content</div>,
          },
        ]}
      />,
    )

    await user.click(screen.getByRole('button', { name: 'Operate' }))

    expect(window.location.pathname).toBe('/money')
    expect(window.location.search).toBe('?symbol=VTI')
  })
})
