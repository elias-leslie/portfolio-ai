import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import type { CaptureMode } from './types'

interface DebugFormProps {
  mode: 'debug'
}

interface NewFeatureFormProps {
  mode: 'new'
  featureName: string
  category: string
  onFeatureNameChange: (name: string) => void
  onCategoryChange: (category: string) => void
}

interface ExistingFeatureFormProps {
  mode: 'existing'
  children: React.ReactNode
}

type ModeFormProps = DebugFormProps | NewFeatureFormProps | ExistingFeatureFormProps

export function ModeForm(props: ModeFormProps) {
  if (props.mode === 'debug') {
    return (
      <div className="rounded-lg border border-primary/30 bg-primary/5 p-4 text-sm space-y-2">
        <p className="font-medium text-primary">Quick Debug - no DB entry</p>
        <ul className="text-muted-foreground text-xs space-y-1">
          <li>• Captures exactly what you see on screen</li>
          <li>• Saves to debug-captures/ with evidence</li>
          <li>• Claude can read: data/debug-captures/latest.png</li>
          <li>• Auto-cleanup keeps last 20 captures</li>
        </ul>
        <p className="text-xs text-warning/80 mt-2">
          A permission popup will appear - select this tab to capture.
        </p>
      </div>
    )
  }

  if (props.mode === 'new') {
    return (
      <div className="space-y-3">
        <div className="rounded-lg border border-border bg-muted/30 p-3 text-xs text-muted-foreground">
          Creates a new feature with your screenshot as evidence.
        </div>
        <div className="space-y-2">
          <Label htmlFor="feature-name" className="text-sm">
            Feature Name
          </Label>
          <Input
            id="feature-name"
            placeholder="e.g., Status Page Services Table"
            value={props.featureName}
            onChange={(e) => props.onFeatureNameChange(e.target.value)}
            className="h-9"
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="feature-category" className="text-sm">
            Category
          </Label>
          <select
            id="feature-category"
            value={props.category}
            onChange={(e) => props.onCategoryChange(e.target.value)}
            className="w-full h-9 px-3 rounded-md border border-input bg-background text-sm"
          >
            <option value="UI">UI</option>
            <option value="Dashboard">Dashboard</option>
            <option value="Status">Status</option>
            <option value="Trading">Trading</option>
            <option value="Portfolio">Portfolio</option>
            <option value="Analytics">Analytics</option>
            <option value="Settings">Settings</option>
          </select>
        </div>
      </div>
    )
  }

  return <>{props.children}</>
}
