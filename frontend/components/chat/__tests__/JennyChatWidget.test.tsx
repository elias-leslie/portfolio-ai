import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ChatWidgetProvider } from '@/components/providers/ChatWidgetProvider'
import { JennyChatWidget } from '../JennyChatWidget'

vi.mock('@/lib/hooks/usePortfolio', () => ({
  useJennyChat: () => ({
    mutateAsync: vi.fn(),
    isPending: false,
  }),
}))

function renderWidget() {
  return render(
    <ChatWidgetProvider>
      <JennyChatWidget />
    </ChatWidgetProvider>,
  )
}

describe('JennyChatWidget', () => {
  beforeEach(() => {
    window.localStorage.clear()
  })

  it('renders the floating bubble when enabled', async () => {
    renderWidget()

    expect(
      await screen.findByRole('button', { name: /open jenny chat/i }),
    ).toBeInTheDocument()
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('expands into the chat panel when the bubble is clicked', async () => {
    const user = userEvent.setup()
    renderWidget()

    await user.click(
      await screen.findByRole('button', { name: /open jenny chat/i }),
    )

    expect(
      screen.getByRole('dialog', { name: /jenny chat/i }),
    ).toBeInTheDocument()
    expect(screen.getByText('Chat with Jenny')).toBeInTheDocument()
  })

  it('collapses via the close button and via Escape', async () => {
    const user = userEvent.setup()
    renderWidget()

    await user.click(
      await screen.findByRole('button', { name: /open jenny chat/i }),
    )
    await user.click(screen.getByRole('button', { name: /close jenny chat/i }))

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: /open jenny chat/i }),
    ).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /open jenny chat/i }))
    expect(
      screen.getByRole('dialog', { name: /jenny chat/i }),
    ).toBeInTheDocument()

    await user.keyboard('{Escape}')
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('renders nothing when the widget is disabled', async () => {
    window.localStorage.setItem(
      'portfolio-ai:jenny-chat:widget-enabled',
      'false',
    )
    renderWidget()

    await waitFor(() =>
      expect(
        screen.queryByRole('button', { name: /open jenny chat/i }),
      ).not.toBeInTheDocument(),
    )
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })
})
