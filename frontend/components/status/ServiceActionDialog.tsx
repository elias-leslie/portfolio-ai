"use client";

import { useState } from "react";
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

interface ServiceActionDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description: string;
  actionLabel?: string;
  onConfirm: () => void;
  storageKey?: string;
}

export function ServiceActionDialog({
  open,
  onOpenChange,
  title,
  description,
  actionLabel = "Continue",
  onConfirm,
  storageKey,
}: ServiceActionDialogProps) {
  const [dontAskAgain, setDontAskAgain] = useState(false);

  const handleConfirm = () => {
    if (dontAskAgain && storageKey) {
      localStorage.setItem(storageKey, "true");
    }
    onConfirm();
    onOpenChange(false);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>{description}</DialogDescription>
        </DialogHeader>
        {storageKey && (
          <div className="flex items-center space-x-2">
            <Checkbox
              id="dont-ask"
              checked={dontAskAgain}
              onCheckedChange={(checked) =>
                setDontAskAgain(checked as boolean)
              }
            />
            <Label htmlFor="dont-ask" className="text-sm cursor-pointer">
              Don&apos;t ask me again
            </Label>
          </div>
        )}
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={handleConfirm}>
            {actionLabel}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
