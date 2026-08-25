'use client'

import { useEffect, useState } from 'react'
import { SectionCard } from '@/components/shared/SectionCard'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import type { PushSubscriptionView } from '@/lib/api/push'
import {
  useDevicePushState,
  useDisablePushOnThisDevice,
  useEnablePushOnThisDevice,
  usePushSubscriptions,
  useRemovePushSubscription,
  useSendTestPush,
} from '@/lib/hooks/usePushAlerts'

/**
 * Which row belongs to the browser reading the card.
 *
 * The endpoint is a bearer capability, so the server never sends it back and no
 * response can identify this handset. The id of the row this device created is
 * the one fact only this device has, so it is kept here.
 */
const THIS_DEVICE_KEY = 'portfolio-ai:push-subscription-id'

function readThisDeviceId(): string | null {
  try {
    return window.localStorage.getItem(THIS_DEVICE_KEY)
  } catch {
    return null
  }
}

function writeThisDeviceId(id: string | null): void {
  try {
    if (id) window.localStorage.setItem(THIS_DEVICE_KEY, id)
    else window.localStorage.removeItem(THIS_DEVICE_KEY)
  } catch {
    // A browser refusing storage still gets alerts; it just cannot label the
    // row as its own.
  }
}

function formatWhen(value: string | null): string | null {
  if (!value) return null
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return null
  return parsed.toLocaleDateString(undefined, {
    month: 'short',
    day: 'numeric',
  })
}

function deviceStatus(device: PushSubscriptionView): {
  label: string
  variant: 'success' | 'warning' | 'outline'
} {
  if (device.lastError) {
    return { label: 'Last send failed', variant: 'warning' }
  }
  const when = formatWhen(device.lastSuccessAt)
  if (when) return { label: `Last alert ${when}`, variant: 'success' }
  return { label: 'No alert sent yet', variant: 'outline' }
}

/**
 * Where a phone says yes to budget alerts (D11, D19).
 *
 * The alerts themselves are not new — they have been landing in the inbox one
 * card down all along, which is a place someone has to already be looking. What
 * this adds is the phone: a subscription belongs to one device, so Elias's
 * Pixel and Mariana's Galaxy register separately and an alert can reach one of
 * them without reaching both. The shared chat it replaces had no recipient at
 * all, so everything went to everyone or to nobody.
 */
export function PushAlertsCard() {
  const { data, isLoading } = usePushSubscriptions()
  const device = useDevicePushState()
  const enable = useEnablePushOnThisDevice()
  const disable = useDisablePushOnThisDevice()
  const remove = useRemovePushSubscription()
  const test = useSendTestPush()

  const [recipientId, setRecipientId] = useState<string | null>(null)
  const [thisDeviceId, setThisDeviceId] = useState<string | null>(null)

  useEffect(() => {
    setThisDeviceId(readThisDeviceId())
  }, [])

  const recipients = data?.recipients ?? []
  const subscriptions = data?.subscriptions ?? []
  const subscribedHere = device.endpoint !== null

  // Default to whoever this device already belongs to, so re-registering does
  // not silently hand the phone to the first name in the list.
  const knownRecipient =
    subscriptions.find((row) => row.id === thisDeviceId)?.householdMemberId ??
    null
  const selectedRecipient = recipientId ?? knownRecipient ?? null

  function turnOn() {
    if (!data?.publicKey) return
    enable.mutate(
      { publicKey: data.publicKey, householdMemberId: selectedRecipient },
      {
        onSuccess: (created) => {
          writeThisDeviceId(created.id)
          setThisDeviceId(created.id)
        },
      },
    )
  }

  function turnOff() {
    disable.mutate(undefined, {
      onSuccess: () => {
        writeThisDeviceId(null)
        setThisDeviceId(null)
      },
    })
  }

  return (
    <SectionCard
      variant="surface"
      title="Alerts on your phone"
      description="Each phone subscribes on its own, so an alert can go to one of you without going to both."
    >
      <div className="space-y-4">
        {isLoading || device.isLoading ? (
          <p className="text-sm text-text-muted">Checking this device…</p>
        ) : (
          <ThisDevice
            enabled={data?.enabled ?? false}
            support={device.support}
            permission={device.permission}
            subscribedHere={subscribedHere}
            recipients={recipients}
            selectedRecipient={selectedRecipient}
            onSelectRecipient={setRecipientId}
            onTurnOn={turnOn}
            onTurnOff={turnOff}
            onTest={() => test.mutate(thisDeviceId)}
            isBusy={enable.isPending || disable.isPending || test.isPending}
          />
        )}

        {subscriptions.length > 0 && (
          <div className="space-y-2">
            <p className="text-xs font-medium uppercase tracking-wide text-text-muted">
              Phones getting alerts
            </p>
            {subscriptions.map((row) => {
              const status = deviceStatus(row)
              return (
                <div
                  key={row.id}
                  className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-border/35 bg-surface-muted/20 px-3 py-2"
                >
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium text-text">
                      {row.memberName ?? 'Unassigned'}
                      {row.deviceLabel ? ` — ${row.deviceLabel}` : ''}
                      {row.id === thisDeviceId ? ' (this phone)' : ''}
                    </p>
                    {/* The badge already carries the send status, so this
                        line says when the phone joined — or what went wrong,
                        which is the one thing the badge cannot spell out. */}
                    <p className="truncate text-xs text-text-muted">
                      {row.lastError ??
                        (formatWhen(row.createdAt)
                          ? `Added ${formatWhen(row.createdAt)}`
                          : 'Registered')}
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <Badge variant={status.variant}>{status.label}</Badge>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => remove.mutate(row.id)}
                      disabled={remove.isPending}
                    >
                      Remove
                    </Button>
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>
    </SectionCard>
  )
}

function ThisDevice({
  enabled,
  support,
  permission,
  subscribedHere,
  recipients,
  selectedRecipient,
  onSelectRecipient,
  onTurnOn,
  onTurnOff,
  onTest,
  isBusy,
}: {
  enabled: boolean
  support: string
  permission: string
  subscribedHere: boolean
  recipients: { id: string; name: string }[]
  selectedRecipient: string | null
  onSelectRecipient: (id: string) => void
  onTurnOn: () => void
  onTurnOff: () => void
  onTest: () => void
  isBusy: boolean
}) {
  // Each of these is a different problem with a different fix, so none of them
  // gets to be a button that can only fail.
  if (!enabled) {
    return (
      <p className="text-sm text-text-muted">
        Push is not configured on the server yet, so no phone can subscribe. Set
        the VAPID keys and this card turns on.
      </p>
    )
  }
  if (support === 'insecure-context') {
    return (
      <p className="text-sm text-text-muted">
        Notifications need a secure connection. Open this app over HTTPS on the
        phone and the option appears here.
      </p>
    )
  }
  if (support !== 'supported') {
    return (
      <p className="text-sm text-text-muted">
        This browser cannot receive push notifications. Chrome on Android can.
      </p>
    )
  }
  if (permission === 'denied') {
    return (
      <p className="text-sm text-text-muted">
        This phone blocked notifications. Allow them for this site in the
        browser&apos;s site settings, then come back here.
      </p>
    )
  }

  if (subscribedHere) {
    return (
      <div className="flex flex-wrap items-center gap-2">
        <Badge variant="success">Alerts are on for this phone</Badge>
        <Button size="sm" variant="outline" onClick={onTest} disabled={isBusy}>
          Send a test
        </Button>
        <Button size="sm" variant="ghost" onClick={onTurnOff} disabled={isBusy}>
          Turn off on this phone
        </Button>
      </div>
    )
  }

  return (
    <div className="space-y-3">
      <p className="text-sm text-text-muted">Whose phone is this?</p>
      <div className="flex flex-wrap gap-2">
        {recipients.map((recipient) => (
          <Button
            key={recipient.id}
            size="sm"
            variant={selectedRecipient === recipient.id ? 'default' : 'outline'}
            onClick={() => onSelectRecipient(recipient.id)}
          >
            {recipient.name}
          </Button>
        ))}
      </div>
      <Button
        size="sm"
        onClick={onTurnOn}
        disabled={isBusy || selectedRecipient === null}
      >
        Turn on alerts for this phone
      </Button>
    </div>
  )
}
