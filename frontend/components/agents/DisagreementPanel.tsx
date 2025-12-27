'use client';

import { useState } from 'react';
import { AlertTriangle, ArrowRight, Check, X, Blend, MessageSquare } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Textarea } from '@/components/ui/textarea';
import { cn } from '@/lib/utils';

// Note: reason values are snake_case from backend (string values aren't transformed)
export type DisagreementReason = 'factual' | 'logical' | 'risk_assessment' | 'confidence' | 'other';
export type ResolutionType = 'use_generator' | 'use_validator' | 'hybrid' | 'escalate';

interface DisagreementPanelProps {
  validationId: string;
  generatorProvider: string;
  generatorOutput: string;
  generatorConfidence: number | null;
  validatorProvider: string;
  validatorReview: string;
  validatorConfidence: number | null;
  disagreementReasons: DisagreementReason[];
  disagreementDetails: string | null;
  onResolve: (resolution: ResolutionType, finalOutput?: string) => void;
  resolving?: boolean;
  className?: string;
}

const REASON_LABELS: Record<DisagreementReason, { label: string; color: string }> = {
  factual: { label: 'Factual Error', color: 'bg-loss/20 text-loss border-loss/30' },
  logical: { label: 'Logic Issue', color: 'bg-warning/20 text-warning border-warning/30' },
  risk_assessment: { label: 'Risk Assessment', color: 'bg-warning/20 text-warning border-warning/30' },
  confidence: { label: 'Confidence Gap', color: 'bg-accent/20 text-accent border-accent/30' },
  other: { label: 'Other', color: 'bg-neutral/20 text-text-muted border-neutral/30' },
};

const RESOLUTION_OPTIONS: { type: ResolutionType; label: string; description: string; icon: React.ReactNode }[] = [
  {
    type: 'use_generator',
    label: 'Use Generator',
    description: 'Accept original output as-is',
    icon: <Check className="h-4 w-4" />,
  },
  {
    type: 'use_validator',
    label: 'Use Validator',
    description: 'Apply validator corrections',
    icon: <ArrowRight className="h-4 w-4" />,
  },
  {
    type: 'hybrid',
    label: 'Hybrid',
    description: 'Combine both outputs manually',
    icon: <Blend className="h-4 w-4" />,
  },
  {
    type: 'escalate',
    label: 'Escalate',
    description: 'Flag for expert review',
    icon: <MessageSquare className="h-4 w-4" />,
  },
];

export function DisagreementPanel({
  generatorProvider,
  generatorOutput,
  generatorConfidence,
  validatorProvider,
  validatorReview,
  validatorConfidence,
  disagreementReasons,
  disagreementDetails,
  onResolve,
  resolving = false,
  className,
}: DisagreementPanelProps) {
  const [selectedResolution, setSelectedResolution] = useState<ResolutionType | null>(null);
  const [hybridOutput, setHybridOutput] = useState<string>(generatorOutput);
  const [showHybridEditor, setShowHybridEditor] = useState(false);

  const handleResolve = () => {
    if (!selectedResolution) return;

    if (selectedResolution === 'hybrid') {
      onResolve(selectedResolution, hybridOutput);
    } else if (selectedResolution === 'use_generator') {
      onResolve(selectedResolution, generatorOutput);
    } else {
      onResolve(selectedResolution);
    }
  };

  const handleResolutionSelect = (type: ResolutionType) => {
    setSelectedResolution(type);
    if (type === 'hybrid') {
      setShowHybridEditor(true);
    } else {
      setShowHybridEditor(false);
    }
  };

  return (
    <div className={cn('space-y-4', className)}>
      {/* Header */}
      <div className="flex items-center gap-2 text-warning">
        <AlertTriangle className="h-5 w-5" />
        <span className="font-semibold">Agent Disagreement Detected</span>
      </div>

      {/* Disagreement Reasons */}
      <div className="flex flex-wrap gap-2">
        {disagreementReasons.map((reason) => {
          const { label, color } = REASON_LABELS[reason] || REASON_LABELS.other;
          return (
            <Badge key={reason} variant="outline" className={cn('border', color)}>
              {label}
            </Badge>
          );
        })}
      </div>

      {/* Side-by-side Comparison */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Generator Output */}
        <div className="bg-surface/50 rounded-lg p-4 border border-border">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <Badge variant="secondary" className="capitalize">
                {generatorProvider}
              </Badge>
              <span className="text-xs text-text-muted">Generator</span>
            </div>
            {generatorConfidence !== null && (
              <span className="text-xs text-text-muted">
                {(generatorConfidence * 100).toFixed(0)}% confident
              </span>
            )}
          </div>
          <div className="text-sm whitespace-pre-wrap text-text max-h-48 overflow-y-auto">
            {generatorOutput}
          </div>
        </div>

        {/* Validator Review */}
        <div className="bg-surface/50 rounded-lg p-4 border border-border">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <Badge variant="secondary" className="capitalize">
                {validatorProvider}
              </Badge>
              <span className="text-xs text-text-muted">Validator</span>
            </div>
            {validatorConfidence !== null && (
              <span className="text-xs text-text-muted">
                {(validatorConfidence * 100).toFixed(0)}% confident
              </span>
            )}
          </div>
          <div className="text-sm whitespace-pre-wrap text-text max-h-48 overflow-y-auto">
            {validatorReview}
          </div>
        </div>
      </div>

      {/* Disagreement Details */}
      {disagreementDetails && (
        <div className="bg-warning/10 border border-warning/30 rounded-lg p-4">
          <p className="text-sm font-medium text-warning mb-2">Specific Issues:</p>
          <div className="text-sm text-text whitespace-pre-wrap">
            {disagreementDetails}
          </div>
        </div>
      )}

      {/* Resolution Options */}
      <div className="space-y-3">
        <p className="text-sm font-medium text-text">Choose Resolution:</p>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
          {RESOLUTION_OPTIONS.map((option) => (
            <button
              key={option.type}
              onClick={() => handleResolutionSelect(option.type)}
              className={cn(
                'p-3 rounded-lg border text-left transition-all',
                selectedResolution === option.type
                  ? 'bg-primary/20 border-primary text-primary'
                  : 'bg-surface/50 border-border text-text-muted hover:border-border'
              )}
            >
              <div className="flex items-center gap-2 mb-1">
                {option.icon}
                <span className="text-sm font-medium">{option.label}</span>
              </div>
              <p className="text-xs opacity-70">{option.description}</p>
            </button>
          ))}
        </div>
      </div>

      {/* Hybrid Editor */}
      {showHybridEditor && (
        <div className="space-y-2">
          <label className="text-sm font-medium text-text">
            Edit Combined Output:
          </label>
          <Textarea
            value={hybridOutput}
            onChange={(e) => setHybridOutput(e.target.value)}
            className="min-h-[120px] bg-surface border-border text-text"
            placeholder="Combine the best parts of both outputs..."
          />
        </div>
      )}

      {/* Action Buttons */}
      <div className="flex items-center gap-3 pt-2 border-t border-border">
        <Button
          onClick={handleResolve}
          disabled={!selectedResolution || resolving}
          className="bg-primary hover:bg-primary/90"
        >
          {resolving ? (
            <>Resolving...</>
          ) : (
            <>
              <Check className="h-4 w-4 mr-2" />
              Apply Resolution
            </>
          )}
        </Button>
        <Button
          variant="ghost"
          onClick={() => {
            setSelectedResolution(null);
            setShowHybridEditor(false);
          }}
          disabled={resolving}
        >
          <X className="h-4 w-4 mr-2" />
          Cancel
        </Button>
      </div>
    </div>
  );
}
