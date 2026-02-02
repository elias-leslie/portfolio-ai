import { useCallback, useState } from 'react'
import { toast } from 'sonner'
import { SUMMITFLOW_API } from '../constants'
import { gatherClientSideEvidence } from './utils'
import { useScreenCapture } from './useScreenCapture'
import type { EvidenceCaptureResult } from './types'

export function useEvidenceCapture(
  pageUrl: string,
  onClose: () => void,
  onCaptured: (result: EvidenceCaptureResult) => void,
) {
  const [isCapturing, setIsCapturing] = useState(false)
  const { captureScreenshotBase64 } = useScreenCapture(onClose)

  // Quick Debug capture - saves to debug folder with evidence (no DB entry)
  const captureDebug = useCallback(async () => {
    setIsCapturing(true)

    try {
      const clientEvidence = gatherClientSideEvidence()
      const base64 = await captureScreenshotBase64()

      const response = await fetch(`${SUMMITFLOW_API}/evidence/debug-capture`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          screenshotBase64: base64,
          url: pageUrl,
          pageTitle: document.title,
          clientEvidence: clientEvidence,
        }),
      })

      if (!response.ok) throw new Error('Failed to upload screenshot')

      const result = await response.json()
      toast.success(
        `Debug captured! Claude: Read data/debug-captures/latest.png`,
      )
      onCaptured({
        success: true,
        version: 1,
        featureId: 'DEBUG',
        criterionId: 'debug',
        evidence: {
          console: clientEvidence.console,
          network: clientEvidence.network,
          metadata: { url: pageUrl, capturedAt: new Date().toISOString() },
        },
        ...result,
      })
    } catch (error) {
      console.error('Debug capture failed:', error)
      if (error instanceof Error && error.name === 'NotAllowedError') {
        toast.error('Screen capture cancelled - permission required')
      } else if (
        error instanceof Error &&
        error.message.includes('chrome://flags')
      ) {
        toast.error(error.message, { duration: 10000 })
      } else {
        toast.error(
          error instanceof Error ? error.message : 'Failed to capture',
        )
      }
    } finally {
      setIsCapturing(false)
    }
  }, [pageUrl, onCaptured, captureScreenshotBase64])

  // Feature capture - saves to feature/criterion with DB entry
  const captureForFeature = useCallback(
    async (featureId: string, criterionId: string) => {
      setIsCapturing(true)

      try {
        // Gather evidence BEFORE screenshot (while page is in current state)
        const clientEvidence = gatherClientSideEvidence()

        const base64 = await captureScreenshotBase64()

        // Send to viewport-capture endpoint (creates DB entry for feature)
        const response = await fetch(
          `${SUMMITFLOW_API}/evidence/viewport-capture`,
          {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              featureId: featureId,
              criterionId: criterionId,
              screenshotBase64: base64,
              url: pageUrl,
              viewportWidth: window.innerWidth,
              viewportHeight: window.innerHeight,
              scrollX: window.scrollX,
              scrollY: window.scrollY,
              pageTitle: document.title,
              clientEvidence: clientEvidence,
            }),
          },
        )

        if (!response.ok) {
          throw new Error('Failed to upload screenshot')
        }

        const result = await response.json()
        toast.success(`Evidence captured (v${result.version}) for ${featureId}`)
        onCaptured(result)
      } catch (error) {
        console.error('Feature capture failed:', error)
        if (error instanceof Error && error.name === 'NotAllowedError') {
          toast.error('Screen capture cancelled - permission required')
        } else if (
          error instanceof Error &&
          error.message.includes('chrome://flags')
        ) {
          toast.error(error.message, { duration: 10000 })
        } else {
          toast.error(
            error instanceof Error
              ? error.message
              : 'Failed to capture evidence',
          )
        }
      } finally {
        setIsCapturing(false)
      }
    },
    [pageUrl, onCaptured, captureScreenshotBase64],
  )

  return { isCapturing, captureDebug, captureForFeature }
}
