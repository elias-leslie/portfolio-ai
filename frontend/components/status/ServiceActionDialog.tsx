"use client";

import {
  ConfirmActionDialog,
  type ConfirmActionDialogProps,
} from "@/components/shared/ConfirmActionDialog";

type ServiceActionDialogProps = Omit<
  ConfirmActionDialogProps,
  "tone" | "confirmLabel" | "rememberChoiceKey" | "rememberChoiceLabel"
> & {
  actionLabel?: string;
  storageKey?: string;
};

export function ServiceActionDialog({
  actionLabel = "Continue",
  storageKey,
  ...props
}: ServiceActionDialogProps) {
  return (
    <ConfirmActionDialog
      {...props}
      tone="default"
      confirmLabel={actionLabel}
      rememberChoiceKey={storageKey}
      rememberChoiceLabel="Don't ask me again"
    />
  );
}
