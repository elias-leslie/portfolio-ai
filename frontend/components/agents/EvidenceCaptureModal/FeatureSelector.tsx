import {
  ArrowDown,
  ArrowUp,
  ArrowUpDown,
  CheckCircle2,
  Link2,
  Loader2,
  Search,
} from 'lucide-react'
import { Checkbox } from '@/components/ui/checkbox'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { ScrollArea } from '@/components/ui/scroll-area'
import { cn } from '@/lib/utils'
import type { ProcessedFeature, SortField, SortDirection } from './types'

interface FeatureSelectorProps {
  features: ProcessedFeature[]
  selectedFeature: string
  selectedCriterion: string
  searchQuery: string
  urlMatchOnly: boolean
  sortField: SortField
  sortDirection: SortDirection
  loading: boolean
  onFeatureSelect: (featureId: string) => void
  onCriterionSelect: (criterionId: string) => void
  onSearchChange: (query: string) => void
  onUrlMatchChange: (checked: boolean) => void
  onSort: (field: SortField) => void
  urlMatchCount: number
}

export function FeatureSelector({
  features,
  selectedFeature,
  selectedCriterion,
  searchQuery,
  urlMatchOnly,
  sortField,
  sortDirection,
  loading,
  onFeatureSelect,
  onCriterionSelect,
  onSearchChange,
  onUrlMatchChange,
  onSort,
  urlMatchCount,
}: FeatureSelectorProps) {
  const selectedFeatureData = features.find(
    (f) => f.featureId === selectedFeature,
  )

  const SortIcon = ({ field }: { field: SortField }) => {
    if (sortField !== field)
      return <ArrowUpDown className="h-3 w-3 opacity-50" />
    return sortDirection === 'asc' ? (
      <ArrowUp className="h-3 w-3" />
    ) : (
      <ArrowDown className="h-3 w-3" />
    )
  }

  return (
    <div className="space-y-3">
      {/* Search and filter controls */}
      <div className="flex gap-2">
        <div className="relative flex-1">
          <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search features..."
            value={searchQuery}
            onChange={(e) => onSearchChange(e.target.value)}
            className="pl-9 h-9"
          />
        </div>
        <div className="flex items-center gap-2 px-3 border rounded-md bg-muted/30">
          <Checkbox
            id="url-match"
            checked={urlMatchOnly}
            onCheckedChange={(c) => onUrlMatchChange(c === true)}
          />
          <Label
            htmlFor="url-match"
            className="text-xs cursor-pointer whitespace-nowrap"
          >
            <Link2 className="h-3 w-3 inline mr-1" />
            URL match only
          </Label>
        </div>
      </div>

      {/* Features table */}
      <div className="border rounded-md">
        {/* Table header */}
        <div className="grid grid-cols-[1fr_2fr_1fr_60px_50px] gap-2 px-3 py-2 bg-muted/50 border-b text-xs font-medium">
          <button
            className="flex items-center gap-1 hover:text-foreground text-left"
            onClick={() => onSort('feature_id')}
          >
            ID <SortIcon field="feature_id" />
          </button>
          <button
            className="flex items-center gap-1 hover:text-foreground text-left"
            onClick={() => onSort('name')}
          >
            Name <SortIcon field="name" />
          </button>
          <button
            className="flex items-center gap-1 hover:text-foreground text-left"
            onClick={() => onSort('category')}
          >
            Category <SortIcon field="category" />
          </button>
          <button
            className="flex items-center gap-1 hover:text-foreground text-center justify-center"
            onClick={() => onSort('ui_count')}
          >
            UI <SortIcon field="ui_count" />
          </button>
          <button
            className="flex items-center gap-1 hover:text-foreground text-center justify-center"
            onClick={() => onSort('url_match')}
            title="URL Match"
          >
            <Link2 className="h-3 w-3" /> <SortIcon field="url_match" />
          </button>
        </div>

        {/* Table body */}
        <ScrollArea className="h-[280px]">
          {loading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
            </div>
          ) : features.length === 0 ? (
            <div className="text-center py-8 text-sm text-muted-foreground">
              {searchQuery || urlMatchOnly
                ? 'No features match your filters'
                : 'No features with UI criteria found'}
            </div>
          ) : (
            features.map((feature) => (
              <button
                key={feature.featureId}
                className={cn(
                  'w-full grid grid-cols-[1fr_2fr_1fr_60px_50px] gap-2 px-3 py-2 text-xs text-left',
                  'hover:bg-muted/50 border-b border-border/50 transition-colors',
                  selectedFeature === feature.featureId &&
                    'bg-accent/10 hover:bg-accent/20',
                )}
                onClick={() => onFeatureSelect(feature.featureId)}
              >
                <span className="font-mono truncate">{feature.featureId}</span>
                <span className="truncate">{feature.name}</span>
                <span className="truncate text-muted-foreground">
                  {feature.category}
                </span>
                <span className="text-center">{feature.uiCount}</span>
                <span className="text-center">
                  {feature.urlMatch && (
                    <Link2 className="h-3.5 w-3.5 text-gain mx-auto" />
                  )}
                </span>
              </button>
            ))
          )}
        </ScrollArea>
      </div>

      {/* Selected feature criteria */}
      {selectedFeatureData && (
        <div className="space-y-2">
          <Label className="text-xs text-muted-foreground">
            Select UI Criterion for{' '}
            <span className="font-mono">{selectedFeature}</span>:
          </Label>
          <div className="border rounded-md divide-y max-h-[120px] overflow-y-auto">
            {selectedFeatureData.uiCriteria.map((criterion) => {
              const isMatching =
                selectedFeatureData.matchingCriteriaIds.includes(criterion.id)
              return (
                <button
                  key={criterion.id}
                  className={cn(
                    'w-full flex items-start gap-2 px-3 py-2 text-left text-xs',
                    'hover:bg-muted/50 transition-colors',
                    selectedCriterion === criterion.id &&
                      'bg-accent/10 hover:bg-accent/20',
                  )}
                  onClick={() => onCriterionSelect(criterion.id)}
                >
                  <span
                    className={cn(
                      'font-mono shrink-0 mt-0.5',
                      selectedCriterion === criterion.id && 'text-accent',
                    )}
                  >
                    {criterion.id}
                  </span>
                  <span className="flex-1 line-clamp-2">
                    {criterion.criterion}
                  </span>
                  {isMatching && (
                    <Link2 className="h-3.5 w-3.5 text-gain shrink-0 mt-0.5" />
                  )}
                  {selectedCriterion === criterion.id && (
                    <CheckCircle2 className="h-3.5 w-3.5 text-accent shrink-0 mt-0.5" />
                  )}
                </button>
              )
            })}
          </div>
        </div>
      )}

      {/* Stats */}
      <div className="text-xs text-muted-foreground">
        {features.length} features
        {urlMatchOnly && ` (${urlMatchCount} URL matches)`}
        {selectedFeature && selectedCriterion && (
          <span className="ml-2 text-accent">
            → {selectedFeature} / {selectedCriterion}
          </span>
        )}
      </div>
    </div>
  )
}
