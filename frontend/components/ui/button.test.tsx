import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi } from 'vitest'
import { Button } from './button'

describe('Button', () => {
  it('renders children text', () => {
    render(<Button>Click me</Button>)
    expect(screen.getByText('Click me')).toBeInTheDocument()
  })

  it('handles click events', async () => {
    const handleClick = vi.fn()
    const user = userEvent.setup()

    render(<Button onClick={handleClick}>Click me</Button>)

    await user.click(screen.getByText('Click me'))

    expect(handleClick).toHaveBeenCalledOnce()
  })

  it('applies variant styles correctly', () => {
    const { rerender } = render(<Button variant="destructive">Destructive</Button>)

    const button = screen.getByText('Destructive')
    expect(button).toHaveClass('bg-destructive')

    rerender(<Button variant="outline">Outline</Button>)
    const outlineButton = screen.getByText('Outline')
    expect(outlineButton).toHaveClass('border')
  })

  it('applies size variants correctly', () => {
    render(<Button size="sm">Small</Button>)

    const button = screen.getByText('Small')
    expect(button).toHaveClass('h-8')
  })

  it('supports disabled state', () => {
    const handleClick = vi.fn()

    render(
      <Button disabled onClick={handleClick}>
        Disabled
      </Button>
    )

    const button = screen.getByText('Disabled')

    expect(button).toBeDisabled()
    expect(button).toHaveClass('disabled:pointer-events-none')
  })

  it('renders as child component when asChild is true', () => {
    render(
      <Button asChild>
        <a href="/test">Link</a>
      </Button>
    )

    const link = screen.getByRole('link', { name: 'Link' })
    expect(link).toBeInTheDocument()
    expect(link).toHaveAttribute('href', '/test')
  })

  it('applies custom className', () => {
    render(<Button className="custom-class">Custom</Button>)

    const button = screen.getByText('Custom')
    expect(button).toHaveClass('custom-class')
  })

  it('has correct data attribute', () => {
    render(<Button>Button</Button>)

    const button = screen.getByText('Button')
    expect(button).toHaveAttribute('data-slot', 'button')
  })
})
