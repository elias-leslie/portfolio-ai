import { useCallback } from 'react'

// Shared Screen Capture API logic - captures exactly what user sees
// Returns base64 PNG or throws error
export function useScreenCapture(onClose: () => void) {
  const captureScreenshotBase64 = useCallback(async (): Promise<string> => {
    // Check if Screen Capture API is available (requires secure context)
    if (!navigator.mediaDevices?.getDisplayMedia) {
      const isLocalhost =
        window.location.hostname === 'localhost' ||
        window.location.hostname === '127.0.0.1'
      const msg = isLocalhost
        ? 'Screen Capture API not available in this browser'
        : `Screen Capture requires HTTPS or localhost. To enable for ${window.location.hostname}:\n\n` +
          'Chrome: chrome://flags/#unsafely-treat-insecure-origin-as-secure\n' +
          `Add: http://${window.location.host}`
      throw new Error(msg)
    }

    // IMPORTANT: Close the modal BEFORE triggering screen capture
    // This prevents the modal from appearing in the screenshot
    onClose()

    // Wait for the modal to be removed from DOM
    await new Promise((resolve) => setTimeout(resolve, 150))

    // Request screen capture with preference for current tab
    const stream = await navigator.mediaDevices.getDisplayMedia({
      video: {
        displaySurface: 'browser',
      },
      // @ts-expect-error - preferCurrentTab is a newer API not in all TypeScript defs
      preferCurrentTab: true,
    })

    try {
      const track = stream.getVideoTracks()[0]

      // Use ImageCapture API if available, fallback to video element approach
      let bitmap: ImageBitmap
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const ImageCaptureAPI = (window as any).ImageCapture
      if (typeof ImageCaptureAPI !== 'undefined') {
        const imageCapture = new ImageCaptureAPI(track)
        bitmap = await imageCapture.grabFrame()
      } else {
        // Fallback for browsers without ImageCapture
        const video = document.createElement('video')
        video.srcObject = stream
        video.muted = true
        await video.play()

        // Wait for video to have dimensions
        await new Promise<void>((resolve) => {
          if (video.videoWidth > 0) {
            resolve()
          } else {
            video.onloadedmetadata = () => resolve()
          }
        })

        bitmap = await createImageBitmap(video)
        video.pause()
        video.srcObject = null
      }

      // Stop the stream immediately after capture
      track.stop()

      // Convert bitmap to canvas to get base64 PNG
      const canvas = document.createElement('canvas')
      canvas.width = bitmap.width
      canvas.height = bitmap.height
      const ctx = canvas.getContext('2d')
      if (!ctx) throw new Error('Failed to get canvas context')
      ctx.drawImage(bitmap, 0, 0)
      bitmap.close()

      const dataUrl = canvas.toDataURL('image/png')
      return dataUrl.split(',')[1]
    } finally {
      // Always clean up stream
      stream.getTracks().forEach((t) => t.stop())
    }
  }, [onClose])

  return { captureScreenshotBase64 }
}
