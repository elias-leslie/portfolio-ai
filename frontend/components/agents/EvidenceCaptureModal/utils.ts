import type { Feature, ProcessedFeature, SortField, SortDirection } from './types'

// Extract path from URL for matching
export function extractPath(url: string): string {
  try {
    const parsed = new URL(url)
    return parsed.pathname
  } catch {
    // If it's already a path or invalid URL
    return url.startsWith('/') ? url : `/${url}`
  }
}

// Check if a feature/criterion matches the current URL path
export function checkUrlMatch(
  feature: Feature,
  currentPath: string,
): { matches: boolean; matchingCriteria: string[] } {
  const matchingCriteria: string[] = []
  const pathLower = currentPath.toLowerCase()

  for (const criterion of feature.acceptanceCriteria) {
    if (criterion.type !== 'ui') continue

    // Check verification field for URL/path
    const verification = criterion.verification?.toLowerCase() || ''
    const criterionText = criterion.criterion.toLowerCase()

    // Match patterns: "screenshot /watchlist", "/watchlist", "http://...//watchlist"
    if (
      verification.includes(pathLower) ||
      criterionText.includes(pathLower) ||
      // Also check if path segments match (e.g., "watchlist" in "/watchlist/details")
      pathLower
        .split('/')
        .some(
          (segment) =>
            segment &&
            (verification.includes(segment) || criterionText.includes(segment)),
        )
    ) {
      matchingCriteria.push(criterion.id)
    }
  }

  return { matches: matchingCriteria.length > 0, matchingCriteria }
}

// Process features with URL matching
export function processFeatures(
  features: Feature[],
  currentPath: string,
): ProcessedFeature[] {
  return features
    .map((feature) => {
      const uiCriteria = feature.acceptanceCriteria.filter(
        (c) => c.type === 'ui',
      )
      const urlMatchInfo = checkUrlMatch(feature, currentPath)
      return {
        ...feature,
        uiCriteria,
        uiCount: uiCriteria.length,
        urlMatch: urlMatchInfo.matches,
        matchingCriteriaIds: urlMatchInfo.matchingCriteria,
      }
    })
    .filter((f) => f.uiCount > 0) // Only show features with UI criteria
}

// Filter and sort features
export function filterAndSortFeatures(
  features: ProcessedFeature[],
  searchQuery: string,
  urlMatchOnly: boolean,
  sortField: SortField,
  sortDirection: SortDirection,
): ProcessedFeature[] {
  let result = [...features]

  // Search filter
  if (searchQuery) {
    const query = searchQuery.toLowerCase()
    result = result.filter(
      (f) =>
        f.featureId.toLowerCase().includes(query) ||
        f.name.toLowerCase().includes(query) ||
        f.category.toLowerCase().includes(query) ||
        f.uiCriteria.some((c) => c.criterion.toLowerCase().includes(query)),
    )
  }

  // URL match filter
  if (urlMatchOnly) {
    result = result.filter((f) => f.urlMatch)
  }

  // Sort
  result.sort((a, b) => {
    let comparison = 0
    switch (sortField) {
      case 'feature_id':
        comparison = a.featureId.localeCompare(b.featureId)
        break
      case 'name':
        comparison = a.name.localeCompare(b.name)
        break
      case 'category':
        comparison = a.category.localeCompare(b.category)
        break
      case 'ui_count':
        comparison = a.uiCount - b.uiCount
        break
      case 'url_match':
        // URL matches first, then by feature ID
        comparison = (b.urlMatch ? 1 : 0) - (a.urlMatch ? 1 : 0)
        if (comparison === 0) {
          comparison = a.featureId.localeCompare(b.featureId)
        }
        break
    }
    return sortDirection === 'asc' ? comparison : -comparison
  })

  return result
}

// Gather client-side console errors and network failures
export function gatherClientSideEvidence() {
  const errors: string[] = []
  const warnings: string[] = []
  const networkFailures: Array<{
    url: string
    status: number
    statusText: string
  }> = []

  // Get recent performance entries for failed requests
  if (typeof performance !== 'undefined' && performance.getEntriesByType) {
    const resources = performance.getEntriesByType(
      'resource',
    ) as PerformanceResourceTiming[]
    // Check for resources that took too long or had issues (heuristic)
    resources.forEach((r) => {
      // Resources with 0 transferSize but non-zero duration might have failed
      // This is imperfect but catches some failures
      if (
        r.transferSize === 0 &&
        r.duration > 0 &&
        r.responseStatus &&
        r.responseStatus >= 400
      ) {
        networkFailures.push({
          url: r.name,
          status: r.responseStatus || 0,
          statusText: 'Failed',
        })
      }
    })
  }

  // Check for any error elements on page (error boundaries, etc.)
  const errorElements = document.querySelectorAll(
    '[data-error], .error, [role="alert"]',
  )
  errorElements.forEach((el) => {
    const text = el.textContent?.trim()
    if (text && text.length < 500) {
      errors.push(text)
    }
  })

  return {
    console: {
      errors: errors.slice(0, 10),
      warnings: warnings.slice(0, 10),
      errorCount: errors.length,
      warningCount: warnings.length,
    },
    network: {
      failures: networkFailures.slice(0, 10),
      failureCount: networkFailures.length,
    },
  }
}
