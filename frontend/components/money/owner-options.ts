export const OWNER_OPTIONS = [
  'Mariana',
  'Elias',
  'Sophia',
  'Nadia',
  'Oksana',
  'Cats',
  'Nadia/Sophia',
  'Family',
  'Mariana/Elias',
]

export function buildOwnerOptions(observed: Iterable<string>): string[] {
  const owners = new Set(OWNER_OPTIONS)
  const customOwners: string[] = []

  for (const owner of observed) {
    const trimmed = owner.trim()
    if (trimmed && !owners.has(trimmed)) {
      owners.add(trimmed)
      customOwners.push(trimmed)
    }
  }

  return [
    ...OWNER_OPTIONS,
    ...customOwners.sort((left, right) => left.localeCompare(right)),
  ]
}
