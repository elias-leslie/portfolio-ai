"""Pydantic contract package for portfolio canonical service results.

All canonical services in ``app/portfolio`` and ``app/services`` return
contract instances from this package. Internal agents (Jenny, Discovery,
Portfolio Analyzer), the FastAPI routers, and the ``st portfolio`` CLI
must all consume the *same* contracts — this is the single-source-of-
truth boundary the F1/F2/F3 plan revolves around.

Adding a new caller never adds analytics code: only consumption of an
existing contract.
"""
