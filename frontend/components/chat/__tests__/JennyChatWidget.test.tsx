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
    <>
      <button type="button">Background action</button>
      <ChatWidgetProvider>
        <JennyChatWidget />
      </ChatWidgetProvider>
    </>,
  )
}

function setMobileViewport(matches: boolean) {
  window.matchMedia = vi.fn().mockImplementation((query: string) => ({
    matches: query === '(max-width: 639px)' ? matches : false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  }))
}

describe('JennyChatWidget', () => {
  beforeEach(() => {
    window.localStorage.clear()
    setMobileViewport(false)
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
      screen.getByRole('dialog', { name: /chat with jenny/i }),
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
      screen.getByRole('dialog', { name: /chat with jenny/i }),
    ).toBeInTheDocument()

    await user.keyboard('{Escape}')
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('contains focus and restores it to the opener on mobile', async () => {
    setMobileViewport(true)
    const user = userEvent.setup()
    renderWidget()

    const opener = await screen.findByRole('button', {
      name: /open jenny chat/i,
    })
    await user.click(opener)

    const close = screen.getByRole('button', { name: /close jenny chat/i })
    const message = screen.getByPlaceholderText(
      /ask anything about portfolio-ai/i,
    )
    await waitFor(() => expect(close).toHaveFocus())

    await user.tab()
    expect(message).toHaveFocus()
    await user.tab()
    expect(close).toHaveFocus()

    await user.keyboard('{Escape}')
    await waitFor(() => expect(opener).toHaveFocus())
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('blocks background interaction and dismisses from the backdrop on mobile', async () => {
    setMobileViewport(true)
    const user = userEvent.setup()
    renderWidget()

    const backgroundAction = screen.getByRole('button', {
      name: /background action/i,
    })
    const opener = await screen.findByRole('button', {
      name: /open jenny chat/i,
    })
    await user.click(opener)

    await waitFor(() =>
      expect(backgroundAction.closest('[aria-hidden="true"]')).not.toBeNull(),
    )

    const overlay = document.querySelector<HTMLElement>(
      '[data-slot="dialog-overlay"]',
    )
    expect(overlay).not.toBeNull()
    await user.click(overlay as HTMLElement)

    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
    expect(backgroundAction.closest('[aria-hidden="true"]')).toBeNull()
    expect(opener).toHaveFocus()
  })

  it('keeps the background available for the desktop chat panel', async () => {
    const user = userEvent.setup()
    renderWidget()

    const backgroundAction = screen.getByRole('button', {
      name: /background action/i,
    })
    await user.click(
      await screen.findByRole('button', { name: /open jenny chat/i }),
    )

    expect(
      screen.getByRole('dialog', { name: /chat with jenny/i }),
    ).toBeVisible()
    expect(backgroundAction.closest('[aria-hidden="true"]')).toBeNull()
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
