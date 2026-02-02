'use client'

import { useQuery } from '@tanstack/react-query'
import { Camera, Crosshair, FolderOpen, Loader2, Zap } from 'lucide-react'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { cn } from '@/lib/utils'
import { SUMMITFLOW_API } from '../constants'
import { FeatureSelector } from './FeatureSelector'
import { ModeForm } from './ModeForm'
import type {
  CaptureMode,
  EvidenceCaptureResult,
  Feature,
  SortDirection,
  SortField,
} from './types'
import { useEvidenceCapture } from './useEvidenceCapture'
import { extractPath, filterAndSortFeatures, processFeatures } from './utils'

interface EvidenceCaptureModalProps {
  open: boolean
  onClose: () => void
  pageUrl: string
  onCaptured: (result: EvidenceCaptureResult) => void
}

export function EvidenceCaptureModal({
  open,
  onClose,
  pageUrl,
  onCaptured,
}: EvidenceCaptureModalProps) {
  const [mode, setMode] = useState<CaptureMode>('debug')
  const [selectedFeature, setSelectedFeature] = useState<string>('')
  const [selectedCriterion, setSelectedCriterion] = useState<string>('')
  const [searchQuery, setSearchQuery] = useState('')
  const [urlMatchOnly, setUrlMatchOnly] = useState(false)
  const [sortField, setSortField] = useState<SortField>('url_match')
  const [sortDirection, setSortDirection] = useState<SortDirection>('desc')
  const [newFeatureName, setNewFeatureName] = useState('')
  const [newFeatureCategory, setNewFeatureCategory] = useState('UI')

  const currentPath = extractPath(pageUrl)
  const { isCapturing, captureDebug, captureForFeature } = useEvidenceCapture(
    pageUrl,
    onClose,
    onCaptured,
  )

  // Fetch existing features
  const { data: featuresData, isLoading: loadingFeatures } = useQuery<{
    features: Feature[]
  }>({
    queryKey: ['features-for-evidence'],
    queryFn: async () => {
      const response = await fetch(`${SUMMITFLOW_API}/features?limit=200`)
      if (!response.ok) throw new Error('Failed to fetch features')
      return response.json()
    },
    enabled: open && mode === 'existing',
  })

  // Process features with URL matching
  const processedFeatures = useMemo(() => {
    if (!featuresData?.features) return []
    return processFeatures(featuresData.features, currentPath)
  }, [featuresData, currentPath])

  // Filter and sort features
  const filteredFeatures = useMemo(() => {
    return filterAndSortFeatures(
      processedFeatures,
      searchQuery,
      urlMatchOnly,
      sortField,
      sortDirection,
    )
  }, [processedFeatures, searchQuery, urlMatchOnly, sortField, sortDirection])

  // Get selected feature data
  const selectedFeatureData = processedFeatures.find(
    (f) => f.featureId === selectedFeature,
  )

  // Reset state when modal opens/closes
  useEffect(() => {
    if (!open) {
      setMode('debug')
      setSelectedFeature('')
      setSelectedCriterion('')
      setSearchQuery('')
      setUrlMatchOnly(false)
    }
  }, [open])

  // Auto-select first matching criterion when feature is selected
  useEffect(() => {
    if (selectedFeatureData && !selectedCriterion) {
      if (selectedFeatureData.matchingCriteriaIds.length > 0) {
        setSelectedCriterion(selectedFeatureData.matchingCriteriaIds[0])
      } else if (selectedFeatureData.uiCriteria.length > 0) {
        setSelectedCriterion(selectedFeatureData.uiCriteria[0].id)
      }
    }
  }, [selectedFeatureData, selectedCriterion])

  // Handle capture - ALL modes use Screen Capture API
  const handleCapture = async () => {
    if (mode === 'debug') {
      await captureDebug()
    } else if (mode === 'new') {
      if (!newFeatureName.trim()) {
        toast.error('Please enter a feature name')
        return
      }
      try {
        const response = await fetch(`${SUMMITFLOW_API}/features`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            name: newFeatureName.trim(),
            category: newFeatureCategory,
            description: `Evidence capture for ${currentPath}`,
            acceptanceCriteria: [
              {
                criterion: `Screenshot of ${currentPath}`,
                type: 'ui',
                verification: pageUrl,
              },
            ],
          }),
        })
        if (!response.ok) throw new Error('Failed to create feature')
        const newFeature = await response.json()
        const criterionId = newFeature.acceptanceCriteria?.[0]?.id || 'ac-001'
        await captureForFeature(newFeature.featureId, criterionId)
      } catch (error) {
        toast.error(
          error instanceof Error ? error.message : 'Failed to create feature',
        )
      }
    } else {
      if (!selectedFeature || !selectedCriterion) {
        toast.error('Please select a feature and criterion')
        return
      }
      await captureForFeature(selectedFeature, selectedCriterion)
    }
  }

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDirection((d) => (d === 'asc' ? 'desc' : 'asc'))
    } else {
      setSortField(field)
      setSortDirection(field === 'url_match' ? 'desc' : 'asc')
    }
  }

  const handleFeatureSelect = useCallback((featureId: string) => {
    setSelectedFeature(featureId)
    setSelectedCriterion('')
  }, [])

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent
        className={cn(
          'sm:max-w-md transition-all duration-200',
          mode === 'existing' && 'sm:max-w-2xl',
        )}
      >
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Camera className="h-5 w-5" />
            Capture Evidence
          </DialogTitle>
          <DialogDescription>
            Capture screenshot and page state for:{' '}
            <code className="text-xs bg-muted px-1 rounded">{currentPath}</code>
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-4">
          {/* Mode selector */}
          <div className="flex gap-2">
            <Button
              variant={mode === 'debug' ? 'default' : 'outline'}
              size="sm"
              onClick={() => setMode('debug')}
              className="flex-1"
            >
              <Zap className="h-4 w-4 mr-2" />
              Quick Debug
            </Button>
            <Button
              variant={mode === 'new' ? 'default' : 'outline'}
              size="sm"
              onClick={() => setMode('new')}
              className="flex-1"
            >
              <Crosshair className="h-4 w-4 mr-2" />
              New Feature
            </Button>
            <Button
              variant={mode === 'existing' ? 'default' : 'outline'}
              size="sm"
              onClick={() => setMode('existing')}
              className="flex-1"
            >
              <FolderOpen className="h-4 w-4 mr-2" />
              Existing
            </Button>
          </div>

          {mode === 'debug' ? (
            <ModeForm mode="debug" />
          ) : mode === 'new' ? (
            <ModeForm
              mode="new"
              featureName={newFeatureName}
              category={newFeatureCategory}
              onFeatureNameChange={setNewFeatureName}
              onCategoryChange={setNewFeatureCategory}
            />
          ) : (
            <ModeForm mode="existing">
              <FeatureSelector
                features={filteredFeatures}
                selectedFeature={selectedFeature}
                selectedCriterion={selectedCriterion}
                searchQuery={searchQuery}
                urlMatchOnly={urlMatchOnly}
                sortField={sortField}
                sortDirection={sortDirection}
                loading={loadingFeatures}
                onFeatureSelect={handleFeatureSelect}
                onCriterionSelect={setSelectedCriterion}
                onSearchChange={setSearchQuery}
                onUrlMatchChange={setUrlMatchOnly}
                onSort={handleSort}
                urlMatchCount={processedFeatures.filter((f) => f.urlMatch).length}
              />
            </ModeForm>
          )}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onClose} disabled={isCapturing}>
            Cancel
          </Button>
          <Button
            onClick={handleCapture}
            disabled={
              isCapturing ||
              (mode === 'new' && !newFeatureName.trim()) ||
              (mode === 'existing' && (!selectedFeature || !selectedCriterion))
            }
          >
            {isCapturing ? (
              <>
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                Capturing...
              </>
            ) : (
              <>
                <Camera className="h-4 w-4 mr-2" />
                Capture
              </>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
