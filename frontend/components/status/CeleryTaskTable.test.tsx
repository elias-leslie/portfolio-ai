import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { CeleryTaskTable } from './CeleryTaskTable'

vi.mock('@/lib/hooks/useCeleryTasks', () => ({
  useCeleryTasks: vi.fn(() => ({
    data: {
      total: 4,
      activeCount: 1,
      pendingCount: 1,
      completedCount: 1,
      failedCount: 1,
      tasks: [
        { id: '1', name: 'run_a', status: 'RUNNING', startedAt: null, duration: null, worker: null, args: null, kwargs: null, result: null, traceback: null, dateDone: null },
        { id: '2', name: 'run_b', status: 'QUEUED', startedAt: null, duration: null, worker: null, args: null, kwargs: null, result: null, traceback: null, dateDone: null },
        { id: '3', name: 'run_c', status: 'SUCCEEDED', startedAt: null, duration: null, worker: null, args: null, kwargs: null, result: null, traceback: null, dateDone: null },
        { id: '4', name: 'run_d', status: 'FAILED', startedAt: null, duration: null, worker: null, args: null, kwargs: null, result: null, traceback: null, dateDone: null },
      ],
    },
    refetch: vi.fn(),
    isLoading: false,
    isFetching: false,
  })),
}))

describe('CeleryTaskTable', () => {
  it('renders workflow statuses with normalized labels', () => {
    render(<CeleryTaskTable />)

    expect(screen.getByText('Workflow Runs')).toBeInTheDocument()
    expect(screen.getByText('Running')).toBeInTheDocument()
    expect(screen.getByText('Queued')).toBeInTheDocument()
    expect(screen.getByText('Completed')).toBeInTheDocument()
    expect(screen.getByText('Failed')).toBeInTheDocument()
  })
})
