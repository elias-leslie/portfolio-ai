"""L2 quantitative scanner — deterministic, back-testable per-symbol scoring.

Runs daily after the L1 macro gate completes. Gate zone governs behaviour:
``FULL_DEPLOY`` scores the full universe, ``REDUCED`` keeps only
``composite_pct > 75``, and ``DEFENSIVE`` emits an empty run with
``skip_reason='gate_defensive'`` so downstream consumers can act on the
absence rather than guess.
"""
