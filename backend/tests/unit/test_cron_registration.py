"""Guard: every cron-scheduled Hatchet task must be registered in worker.py.

A ``@hatchet.task(on_crons=...)`` whose symbol is absent from worker.py's
``hatchet.worker(workflows=[...])`` list is silently dead: Hatchet only creates a
``WorkflowTriggerCronRef`` for a *registered* workflow, so the declared cron never
fires. That is the household-holdings bug class (added in db578976, removed as
dead code in df5bebd5). See ``[[portfolio-ai-data-freshness-pattern]]``.

This is an OFFLINE AST check — it needs no Hatchet engine and never imports the
workflow modules, so it runs in plain CI. It covers both definition shapes:

  1. a module-level ``def``/``async def`` decorated with ``@hatchet.task(on_crons=...)``
  2. a module-level binding ``NAME = factory(..., crons, ...)`` where ``factory`` is a
     local function (e.g. maintenance.py ``_empty_wf`` / ``_cleanup_wf``) that applies
     a cron'd ``@hatchet.task`` to a nested ``_wf``. The cron is attributed to the
     binding, not to the inner ``_wf`` (which is never registered by name).

The inverse failure (a cron ref in the engine with no code, i.e. a *zombie*) cannot
be caught offline — it needs engine access; see the data-freshness wiki page.
"""

from __future__ import annotations

import ast
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[2]
WORKFLOWS_DIR = _BACKEND / "app" / "workflows"
WORKER_FILE = _BACKEND / "app" / "worker.py"


def _is_crond_task_decorator(decorator: ast.expr) -> bool:
    """True if ``decorator`` is ``@hatchet.task(...)`` declaring a non-empty on_crons."""
    if not (
        isinstance(decorator, ast.Call)
        and isinstance(decorator.func, ast.Attribute)
        and decorator.func.attr == "task"
    ):
        return False
    for kw in decorator.keywords:
        if kw.arg == "on_crons":
            # An empty list literal declares no crons. A non-empty literal or a
            # constant reference (e.g. DAILY_OHLCV_CRONS) is a real schedule.
            return not (isinstance(kw.value, ast.List) and not kw.value.elts)
    return False


def _builds_on_crons_dict(node: ast.AST) -> bool:
    """True if a dict literal with an ``"on_crons"`` key is built anywhere in ``node``.

    Captures the ``_empty_wf`` pattern where on_crons reaches the decorator via a
    ``**kw`` spread: ``kw = {"on_crons": crons}; @hatchet.task(..., **kw)``.
    """
    for sub in ast.walk(node):
        if isinstance(sub, ast.Dict) and any(
            isinstance(k, ast.Constant) and k.value == "on_crons" for k in sub.keys
        ):
            return True
    return False


def _wraps_crond_task(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """True if a local factory decorates a *nested* fn with a cron'd ``@hatchet.task``.

    Handles both a direct ``on_crons=`` keyword (``_cleanup_wf``) and a ``**kw`` spread
    whose dict carries ``on_crons`` (``_empty_wf``).
    """
    for inner in ast.walk(node):
        if inner is node:
            continue
        if not isinstance(inner, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        for dec in inner.decorator_list:
            if _is_crond_task_decorator(dec):
                return True
            if (
                isinstance(dec, ast.Call)
                and isinstance(dec.func, ast.Attribute)
                and dec.func.attr == "task"
                and any(kw.arg is None for kw in dec.keywords)  # has a **spread
                and _builds_on_crons_dict(node)
            ):
                return True
    return False


def crond_symbols_in_module(source: str) -> set[str]:
    """Module-level symbols that resolve to a cron-scheduled Hatchet workflow."""
    tree = ast.parse(source)

    crond_factories = {
        node.name
        for node in tree.body
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and _wraps_crond_task(node)
    }

    symbols: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            if any(_is_crond_task_decorator(d) for d in node.decorator_list):
                symbols.add(node.name)
        elif isinstance(node, ast.Assign):
            value = node.value
            if (
                isinstance(value, ast.Call)
                and isinstance(value.func, ast.Name)
                and value.func.id in crond_factories
            ):
                symbols.update(t.id for t in node.targets if isinstance(t, ast.Name))
    return symbols


def registered_symbols(worker_source: str) -> set[str]:
    """Names listed in worker.py's ``hatchet.worker(workflows=[...])``."""
    tree = ast.parse(worker_source)
    registered: set[str] = set()
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.keyword)
            and node.arg == "workflows"
            and isinstance(node.value, ast.List)
        ):
            registered.update(e.id for e in node.value.elts if isinstance(e, ast.Name))
    return registered


def _all_crond_symbols() -> set[str]:
    symbols: set[str] = set()
    for path in sorted(WORKFLOWS_DIR.glob("*.py")):
        symbols |= crond_symbols_in_module(path.read_text())
    return symbols


def test_every_crond_task_is_registered_in_worker() -> None:
    dead = sorted(_all_crond_symbols() - registered_symbols(WORKER_FILE.read_text()))
    assert not dead, (
        "These tasks declare on_crons but are absent from worker.py workflows=[...], "
        "so Hatchet never registers their cron and it silently never fires "
        f"(dead-cron / household-holdings bug class): {dead}"
    )


def test_guard_finds_the_known_crond_workflows() -> None:
    # Sanity floor: if the AST detector silently stops matching, this catches it
    # before test_every_crond_task_is_registered_in_worker degrades to vacuously green.
    symbols = _all_crond_symbols()
    for expected in (
        "refresh_daily_ohlcv_wf",  # direct decorator, on_crons=Name constant
        "profile_news_wf",  # direct decorator, on_crons=list literal
        "rotate_logs_wf",  # factory binding (_empty_wf)
        "cleanup_news_wf",  # factory binding (_cleanup_wf)
    ):
        assert expected in symbols, f"detector failed to find cron'd workflow {expected!r}"


# --- detector self-tests: lock the AST logic against silent rot -----------------


def test_detector_flags_direct_crond_task() -> None:
    src = "@hatchet.task(name='a', on_crons=['0 0 * * *'])\ndef alpha_wf(i, c):\n    return 1\n"
    assert crond_symbols_in_module(src) == {"alpha_wf"}


def test_detector_attributes_factory_cron_to_binding_not_inner_wf() -> None:
    src = (
        "def _make(name, crons):\n"
        "    @hatchet.task(name=name, on_crons=crons)\n"
        "    async def _wf(i, c):\n        return 1\n"
        "    return _wf\n"
        "beta_wf = _make('b', ['0 0 * * *'])\n"
    )
    assert crond_symbols_in_module(src) == {"beta_wf"}


def test_detector_handles_factory_passing_on_crons_via_kwargs_spread() -> None:
    # The maintenance.py _empty_wf shape: on_crons reaches the decorator via **kw.
    src = (
        "def _make(name, crons):\n"
        "    kw = {'on_crons': crons}\n"
        "    @hatchet.task(name=name, **kw)\n"
        "    async def _wf(i, c):\n        return 1\n"
        "    return _wf\n"
        "epsilon_wf = _make('e', ['0 0 * * *'])\n"
    )
    assert crond_symbols_in_module(src) == {"epsilon_wf"}


def test_detector_ignores_event_only_task() -> None:
    src = "@hatchet.task(name='c')\ndef gamma_wf(i, c):\n    return 1\n"
    assert crond_symbols_in_module(src) == set()


def test_detector_ignores_empty_on_crons() -> None:
    src = "@hatchet.task(name='d', on_crons=[])\ndef delta_wf(i, c):\n    return 1\n"
    assert crond_symbols_in_module(src) == set()


def test_registered_symbols_parses_worker_list() -> None:
    src = "w = hatchet.worker('x', workflows=[alpha_wf, beta_wf])\n"
    assert registered_symbols(src) == {"alpha_wf", "beta_wf"}
