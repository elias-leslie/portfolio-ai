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

  it('cleans up invalid tab parameters by falling back to the default tab', () => {
    window.history.replaceState({}, '', '/money?symbol=VTI&tab=unknown')

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

    expect(screen.getByText('Operate Content')).toBeInTheDocument()
    expect(window.location.search).toBe('?symbol=VTI')
  })

  it('preserves the hash fragment when changing tabs', async () => {
    const user = userEvent.setup()
    window.history.replaceState({}, '', '/money?symbol=VTI#intake')

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

    expect(window.location.search).toBe('?symbol=VTI&tab=planning')
    expect(window.location.hash).toBe('#intake')
  })

  it('falls back when the active tab disappears from the available tab set', () => {
    const { rerender } = render(
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

    rerender(
      <WorkspaceTabs
        defaultValue="operate"
        tabs={[
          {
            value: 'operate',
            label: 'Operate',
            description: 'Run the day-to-day queue.',
            content: <div>Operate Content</div>,
          },
        ]}
      />,
    )

    expect(screen.getByText('Operate Content')).toBeInTheDocument()
    expect(screen.queryByText('Planning Content')).not.toBeInTheDocument()
  })

  it('reacts to same-page query changes from navigation links', async () => {
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
            value: 'intake',
            label: 'Intake',
            description: 'Upload documents.',
            content: <div>Intake Content</div>,
          },
        ]}
      />,
    )

    window.history.replaceState({}, '', '/money?tab=intake')
    await screen.findByText('Intake Content')
  })

  it('keeps badge counts out of the tab accessible name', () => {
    render(
      <WorkspaceTabs
        defaultValue="operate"
        tabs={[
          {
            value: 'operate',
            label: 'Operate',
            badge: '7',
            description: 'Run the day-to-day queue.',
            content: <div>Operate Content</div>,
          },
        ]}
      />,
    )

    expect(screen.getByRole('button', { name: 'Operate' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Operate7' })).not.toBeInTheDocument()
  })

  it('connects the active tab, description, and panel for assistive tech', () => {
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
        ]}
      />,
    )

    const trigger = screen.getByRole('button', { name: 'Operate' })
    const panel = document.getElementById(trigger.getAttribute('aria-controls') ?? '')

    expect(trigger).toHaveAttribute('aria-describedby')
    expect(panel).toHaveAttribute('aria-labelledby', trigger.getAttribute('id'))
    expect(
      document.getElementById(trigger.getAttribute('aria-describedby') ?? ''),
    ).toHaveTextContent('Run the day-to-day queue.')
  })
})
