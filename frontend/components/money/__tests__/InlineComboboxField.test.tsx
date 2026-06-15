'use client'

import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { describe, expect, it, vi } from 'vitest'
import { InlineComboboxField } from '../InlineComboboxField'

describe('InlineComboboxField', () => {
  it('keeps the rule checkbox checked and commits the current value as a rule', async () => {
    const user = userEvent.setup()
    const handleCommit = vi.fn()

    function Harness() {
      const [checked, setChecked] = useState(false)
      return (
        <InlineComboboxField
          id="category"
          label="Category"
          value="Groceries"
          options={['Groceries', 'Household']}
          onCommit={handleCommit}
          ruleLabel="Merchant rule"
          ruleChecked={checked}
          onRuleCheckedChange={setChecked}
        />
      )
    }

    render(<Harness />)

    const checkbox = screen.getByRole('checkbox', {
      name: 'Merchant rule for Category',
    })
    await user.click(checkbox)

    expect(checkbox).toBeChecked()
    expect(handleCommit).toHaveBeenCalledWith('Groceries', {
      applyRule: true,
    })
  })
})
