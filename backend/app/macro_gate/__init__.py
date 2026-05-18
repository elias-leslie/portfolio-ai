"""L1 macro deployment gate.

Deterministic, back-testable composite of six macro signals that produces a
``deployment_score`` in [0, 100] and a zone classification
(``FULL_DEPLOY`` / ``REDUCED`` / ``DEFENSIVE``). All inputs reuse existing
ingestion (FRED, VIX from fear_greed_inputs, put/call series, sector ETFs)
plus new collectors in ``.signals`` for term structure, SPX breadth, and
factor crowding.
"""
