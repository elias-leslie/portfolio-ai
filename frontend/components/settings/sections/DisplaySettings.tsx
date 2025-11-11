"use client";

import { Monitor, Moon, Sun } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { SectionHeader } from "../SectionHeader";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { cn } from "@/lib/utils";
import { useTheme } from "@/lib/hooks/useTheme";

interface DisplaySettingsProps {
  displayTimezone: string;
  onDisplayTimezoneChange: (value: string) => void;
}

const TIMEZONE_OPTIONS = {
  "America/New_York": "Eastern Time (EST/EDT)",
  "America/Chicago": "Central Time (CST/CDT)",
  "America/Denver": "Mountain Time (MST/MDT)",
  "America/Los_Angeles": "Pacific Time (PST/PDT)",
  "America/Anchorage": "Alaska Time (AKST/AKDT)",
  "Pacific/Honolulu": "Hawaii Time (HST)",
};

export function DisplaySettings({
  displayTimezone,
  onDisplayTimezoneChange,
}: DisplaySettingsProps) {
  const { theme, setTheme } = useTheme();

  return (
    <div className="space-y-6">
      <SectionHeader
        icon={<Monitor className="h-6 w-6" />}
        title="Display & Interface"
        description="Customize how data is displayed across the application"
      />

      {/* Theme Selection */}
      <Card>
        <CardContent className="pt-6">
          <div className="space-y-4">
            <Label>Theme</Label>
            <RadioGroup
              value={theme}
              onValueChange={(value) =>
                setTheme(value as "light" | "dark" | "system")
              }
              className="grid grid-cols-1 gap-3 sm:grid-cols-3"
            >
              <ThemeOption
                value="light"
                icon={<Sun className="h-5 w-5" />}
                label="Light"
                description="Light mode"
              />
              <ThemeOption
                value="dark"
                icon={<Moon className="h-5 w-5" />}
                label="Dark"
                description="Dark mode"
              />
              <ThemeOption
                value="system"
                icon={<Monitor className="h-5 w-5" />}
                label="System"
                description="Follow system"
              />
            </RadioGroup>
          </div>
        </CardContent>
      </Card>

      {/* Timezone */}
      <Card>
        <CardContent className="pt-6">
          <div className="space-y-2">
            <Label htmlFor="timezone">Timezone</Label>
            <Select value={displayTimezone} onValueChange={onDisplayTimezoneChange}>
              <SelectTrigger id="timezone">
                <SelectValue placeholder="Select timezone" />
              </SelectTrigger>
              <SelectContent>
                {Object.entries(TIMEZONE_OPTIONS).map(([value, label]) => (
                  <SelectItem key={value} value={value}>
                    {label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <p className="text-xs text-text-muted">
              Choose your preferred timezone for displaying dates and times
              throughout the application
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

interface ThemeOptionProps {
  value: string;
  icon: React.ReactNode;
  label: string;
  description: string;
}

function ThemeOption({ value, icon, label, description }: ThemeOptionProps) {
  return (
    <label
      htmlFor={`theme-${value}`}
      className="group relative cursor-pointer"
    >
      <RadioGroupItem
        value={value}
        id={`theme-${value}`}
        className="peer sr-only"
      />
      <div
        className={cn(
          "flex flex-col items-center gap-3 rounded-lg border-2 border-border p-4 transition-all",
          "peer-data-[state=checked]:border-primary peer-data-[state=checked]:bg-primary/5",
          "hover:border-border/60 hover:bg-surface-muted/30"
        )}
      >
        <div
          className={cn(
            "flex h-10 w-10 items-center justify-center rounded-full transition-colors",
            "peer-data-[state=checked]:bg-primary/20 peer-data-[state=checked]:text-primary",
            "bg-surface-muted text-text-muted group-hover:bg-surface-muted/60"
          )}
        >
          {icon}
        </div>
        <div className="text-center">
          <p className="font-medium text-text">{label}</p>
          <p className="text-xs text-text-muted">{description}</p>
        </div>
      </div>
    </label>
  );
}
