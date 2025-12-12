'use client';

import { useState, useEffect, useCallback } from 'react';
import { Check, X, Edit, RefreshCw, AlertTriangle, Clock, ChevronDown, ChevronUp } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Textarea } from '@/components/ui/textarea';
import { cn } from '@/lib/utils';
import { DisagreementPanel, DisagreementReason, ResolutionType } from './DisagreementPanel';

interface ValidationResult {
  id: string;
  created_at: string;
  generator_provider: string;
  generator_output: string;
  generator_confidence: number | null;
  validator_provider: string;
  validator_review: string;
  validator_approved: boolean;
  validator_confidence: number | null;
  has_disagreement: boolean;
  disagreement_reasons: string[];
  disagreement_details: string | null;
  status: string;
  resolved_at: string | null;
  resolved_by: string | null;
  final_output: string | null;
  context_type: string;
  context_symbol: string | null;
}

interface ReviewQueueProps {
  className?: string;
}

export function ReviewQueue({ className }: ReviewQueueProps) {
  const [validations, setValidations] = useState<ValidationResult[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editedOutput, setEditedOutput] = useState<string>('');
  const [resolving, setResolving] = useState<string | null>(null);

  const fetchValidations = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await fetch('http://localhost:8000/api/cross-validation/pending');
      if (!res.ok) throw new Error('Failed to fetch validations');
      const data = await res.json();
      setValidations(data.validations || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchValidations();
  }, [fetchValidations]);

  const handleResolve = async (id: string, approved: boolean, finalOutput?: string) => {
    try {
      setResolving(id);
      const res = await fetch(`http://localhost:8000/api/cross-validation/resolve/${id}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          approved,
          final_output: finalOutput || null,
        }),
      });
      if (!res.ok) throw new Error('Failed to resolve validation');

      // Remove from list
      setValidations(prev => prev.filter(v => v.id !== id));
      setExpandedId(null);
      setEditingId(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to resolve');
    } finally {
      setResolving(null);
    }
  };

  const handleEdit = (validation: ValidationResult) => {
    setEditingId(validation.id);
    setEditedOutput(validation.generator_output);
    setExpandedId(validation.id);
  };

  const handleSaveEdit = (id: string) => {
    handleResolve(id, true, editedOutput);
  };

  const handleDisagreementResolve = (
    id: string,
    resolution: ResolutionType,
    finalOutput?: string
  ) => {
    // Map resolution type to approved status
    const approved = resolution !== 'escalate';
    handleResolve(id, approved, finalOutput);
  };

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    return date.toLocaleString();
  };

  if (loading) {
    return (
      <div className={cn('flex items-center justify-center p-8', className)}>
        <RefreshCw className="h-6 w-6 animate-spin text-muted-foreground" />
        <span className="ml-2 text-muted-foreground">Loading review queue...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className={cn('flex flex-col items-center justify-center p-8', className)}>
        <AlertTriangle className="h-8 w-8 text-destructive mb-2" />
        <p className="text-destructive">{error}</p>
        <Button variant="outline" className="mt-4" onClick={fetchValidations}>
          <RefreshCw className="h-4 w-4 mr-2" />
          Retry
        </Button>
      </div>
    );
  }

  if (validations.length === 0) {
    return (
      <div className={cn('flex flex-col items-center justify-center p-8 text-center', className)}>
        <Check className="h-12 w-12 text-green-500 mb-4" />
        <h3 className="text-lg font-semibold">All Caught Up!</h3>
        <p className="text-muted-foreground mt-2">
          No pending validations require review.
        </p>
        <Button variant="outline" className="mt-4" onClick={fetchValidations}>
          <RefreshCw className="h-4 w-4 mr-2" />
          Refresh
        </Button>
      </div>
    );
  }

  return (
    <div className={cn('space-y-4', className)}>
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">
          Review Queue
          <Badge variant="secondary" className="ml-2">
            {validations.length} pending
          </Badge>
        </h2>
        <Button variant="outline" size="sm" onClick={fetchValidations}>
          <RefreshCw className="h-4 w-4 mr-2" />
          Refresh
        </Button>
      </div>

      <div className="space-y-3">
        {validations.map(validation => (
          <Card
            key={validation.id}
            className={cn(
              'transition-all',
              validation.has_disagreement && 'border-amber-500/50'
            )}
          >
            <CardHeader className="py-3 px-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <CardTitle className="text-sm font-medium">
                    {validation.context_type}
                    {validation.context_symbol && (
                      <Badge variant="outline" className="ml-2">
                        {validation.context_symbol}
                      </Badge>
                    )}
                  </CardTitle>
                  {validation.has_disagreement && (
                    <Badge variant="destructive" className="text-xs">
                      <AlertTriangle className="h-3 w-3 mr-1" />
                      Disagreement
                    </Badge>
                  )}
                  {validation.validator_approved && !validation.has_disagreement && (
                    <Badge variant="default" className="text-xs bg-green-600">
                      <Check className="h-3 w-3 mr-1" />
                      Approved
                    </Badge>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-muted-foreground flex items-center">
                    <Clock className="h-3 w-3 mr-1" />
                    {formatDate(validation.created_at)}
                  </span>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setExpandedId(expandedId === validation.id ? null : validation.id)}
                  >
                    {expandedId === validation.id ? (
                      <ChevronUp className="h-4 w-4" />
                    ) : (
                      <ChevronDown className="h-4 w-4" />
                    )}
                  </Button>
                </div>
              </div>
            </CardHeader>

            {expandedId === validation.id && (
              <CardContent className="pt-0 pb-4 px-4 space-y-4">
                {/* Generator Output */}
                <div>
                  <div className="flex items-center gap-2 mb-2">
                    <Badge variant="secondary" className="text-xs">
                      {validation.generator_provider}
                    </Badge>
                    {validation.generator_confidence !== null && (
                      <span className="text-xs text-muted-foreground">
                        Confidence: {(validation.generator_confidence * 100).toFixed(0)}%
                      </span>
                    )}
                  </div>
                  {editingId === validation.id ? (
                    <Textarea
                      value={editedOutput}
                      onChange={(e) => setEditedOutput(e.target.value)}
                      className="min-h-[100px] font-mono text-sm"
                    />
                  ) : (
                    <div className="bg-muted/50 rounded-md p-3 text-sm whitespace-pre-wrap">
                      {validation.generator_output}
                    </div>
                  )}
                </div>

                {/* Validator Review */}
                <div>
                  <div className="flex items-center gap-2 mb-2">
                    <Badge variant="secondary" className="text-xs">
                      {validation.validator_provider} review
                    </Badge>
                    {validation.validator_confidence !== null && (
                      <span className="text-xs text-muted-foreground">
                        Confidence: {(validation.validator_confidence * 100).toFixed(0)}%
                      </span>
                    )}
                  </div>
                  <div className="bg-muted/50 rounded-md p-3 text-sm whitespace-pre-wrap">
                    {validation.validator_review}
                  </div>
                </div>

                {/* Disagreement Panel or Standard Actions */}
                {validation.has_disagreement && validation.disagreement_reasons.length > 0 ? (
                  <DisagreementPanel
                    validationId={validation.id}
                    generatorProvider={validation.generator_provider}
                    generatorOutput={validation.generator_output}
                    generatorConfidence={validation.generator_confidence}
                    validatorProvider={validation.validator_provider}
                    validatorReview={validation.validator_review}
                    validatorConfidence={validation.validator_confidence}
                    disagreementReasons={validation.disagreement_reasons as DisagreementReason[]}
                    disagreementDetails={validation.disagreement_details}
                    onResolve={(resolution, finalOutput) =>
                      handleDisagreementResolve(validation.id, resolution, finalOutput)
                    }
                    resolving={resolving === validation.id}
                  />
                ) : (
                  /* Standard Actions for non-disagreement validations */
                  <div className="flex items-center gap-2 pt-2 border-t">
                    {editingId === validation.id ? (
                      <>
                        <Button
                          size="sm"
                          onClick={() => handleSaveEdit(validation.id)}
                          disabled={resolving === validation.id}
                        >
                          <Check className="h-4 w-4 mr-1" />
                          Save & Accept
                        </Button>
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => {
                            setEditingId(null);
                            setEditedOutput('');
                          }}
                        >
                          Cancel
                        </Button>
                      </>
                    ) : (
                      <>
                        <Button
                          size="sm"
                          variant="default"
                          className="bg-green-600 hover:bg-green-700"
                          onClick={() => handleResolve(validation.id, true)}
                          disabled={resolving === validation.id}
                        >
                          <Check className="h-4 w-4 mr-1" />
                          Accept
                        </Button>
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => handleEdit(validation)}
                          disabled={resolving === validation.id}
                        >
                          <Edit className="h-4 w-4 mr-1" />
                          Modify
                        </Button>
                        <Button
                          size="sm"
                          variant="destructive"
                          onClick={() => handleResolve(validation.id, false)}
                          disabled={resolving === validation.id}
                        >
                          <X className="h-4 w-4 mr-1" />
                          Reject
                        </Button>
                      </>
                    )}
                    {resolving === validation.id && (
                      <RefreshCw className="h-4 w-4 animate-spin ml-2" />
                    )}
                  </div>
                )}
              </CardContent>
            )}
          </Card>
        ))}
      </div>
    </div>
  );
}
