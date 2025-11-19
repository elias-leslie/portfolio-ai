"use client";

import { useEffect, useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import type { ReactNode } from "react";

type DialogTone = "default" | "destructive";

export interface ConfirmActionDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: ReactNode;
  description?: ReactNode;
  confirmLabel?: string;
  cancelLabel?: string;
  tone?: DialogTone;
  isPending?: boolean;
  disableConfirm?: boolean;
  rememberChoiceKey?: string;
  rememberChoiceLabel?: string;
  children?: ReactNode;
  onConfirm: () => void | Promise<void>;
}

/**
 * Shared confirmation dialog so destructive flows feel consistent everywhere.
 */
export function ConfirmActionDialog({
  open,
  onOpenChange,
  title,
  description,
  confirmLabel = "Continue",
  cancelLabel = "Cancel",
  tone = "destructive",
  isPending = false,
  disableConfirm = false,
  rememberChoiceKey,
  rememberChoiceLabel = "Don't ask me again",
  children,
  onConfirm,
}: ConfirmActionDialogProps) {
  const [rememberChoice, setRememberChoice] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    if (!open) {
      setRememberChoice(false);
      setIsSubmitting(false);
    }
  }, [open]);

  const handleConfirm = async () => {
    setIsSubmitting(true);
    try {
      await onConfirm();
      if (rememberChoice && rememberChoiceKey && typeof window !== "undefined") {
        localStorage.setItem(rememberChoiceKey, "true");
      }
      onOpenChange(false);
    } catch (error) {
      console.error(error);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          {description && <DialogDescription>{description}</DialogDescription>}
        </DialogHeader>
        {children}
        {rememberChoiceKey && (
          <div className="flex items-center space-x-2 rounded-md border border-border/50 bg-surface/60 p-3">
            <Checkbox
              id="remember-choice"
              checked={rememberChoice}
              onCheckedChange={(checked) => setRememberChoice(Boolean(checked))}
            />
            <Label
              htmlFor="remember-choice"
              className="cursor-pointer text-sm text-text-muted"
            >
              {rememberChoiceLabel}
            </Label>
          </div>
        )}
        <DialogFooter>
          <Button
            type="button"
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={isPending || isSubmitting}
          >
            {cancelLabel}
          </Button>
          <Button
            type="button"
            variant={tone === "destructive" ? "destructive" : "default"}
            onClick={handleConfirm}
            disabled={disableConfirm || isPending || isSubmitting}
          >
            {isPending || isSubmitting ? "Working..." : confirmLabel}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
