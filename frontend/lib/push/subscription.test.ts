import { describe, expect, it } from 'vitest'
import { deviceLabelFrom, urlBase64ToUint8Array } from './subscription'

describe('deviceLabelFrom', () => {
  it('names the Android handset from the build token', () => {
    // The only string in a user-agent that tells one phone in this household
    // from the other.
    expect(
      deviceLabelFrom(
        'Mozilla/5.0 (Linux; Android 14; Pixel 7 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Mobile Safari/537.36',
      ),
    ).toBe('Pixel 7 Pro')
    expect(
      deviceLabelFrom(
        'Mozilla/5.0 (Linux; Android 14; SM-S908U) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Mobile Safari/537.36',
      ),
    ).toBe('SM-S908U')
  })

  it('strips the Build suffix some devices append', () => {
    expect(
      deviceLabelFrom(
        'Mozilla/5.0 (Linux; Android 11; SM-A515F Build/RP1A) Chrome/126',
      ),
    ).toBe('SM-A515F')
  })

  it('falls back to the browser when Android reports the frozen "K" model', () => {
    // Chrome froze the model string for privacy on newer Android; a label of
    // "K" would name nothing, so the browser is at least true.
    expect(
      deviceLabelFrom(
        'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Mobile Safari/537.36',
      ),
    ).toBe('Chrome on desktop')
  })

  it('names a desktop browser when there is no model at all', () => {
    expect(
      deviceLabelFrom(
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Firefox/128.0',
      ),
    ).toBe('Firefox on desktop')
  })
})

describe('urlBase64ToUint8Array', () => {
  it('decodes the base64url VAPID key the backend serves', () => {
    // "hi" as base64url, unpadded — the form py_vapid emits.
    expect(Array.from(urlBase64ToUint8Array('aGk'))).toEqual([104, 105])
  })

  it('decodes the url-safe alphabet, not just standard base64', () => {
    // 0xFB 0xEF encodes to "++8" in standard base64 and "--8" in base64url; a
    // decoder that skipped the swap would throw or return the wrong key, and a
    // wrong application server key fails only at subscribe time.
    expect(Array.from(urlBase64ToUint8Array('--8'))).toEqual([251, 239])
  })

  it('is backed by a plain ArrayBuffer, which is what subscribe() requires', () => {
    expect(urlBase64ToUint8Array('aGk').buffer).toBeInstanceOf(ArrayBuffer)
  })
})
