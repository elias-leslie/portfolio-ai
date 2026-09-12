import asyncio

import pytest

from app.services.retirement_preview_coordinator import PreviewCoordinator


@pytest.mark.asyncio
async def test_identical_previews_share_work_and_invalidation_recomputes():
    coordinator=PreviewCoordinator()
    calls=[]
    def calculate():
        calls.append(1)
        return {'value':len(calls)}
    first,second=await asyncio.gather(coordinator.get('same',calculate),coordinator.get('same',calculate))
    assert first==second=={'value':1}
    assert await coordinator.get('same',calculate)==first
    assert len(calls)==1
    coordinator.invalidate()
    assert await coordinator.get('same',calculate)=={'value':2}


@pytest.mark.asyncio
async def test_failed_preview_is_retryable():
    coordinator=PreviewCoordinator()
    def fail():
        raise ValueError('invalid inputs')
    with pytest.raises(ValueError):
        await coordinator.get('same',fail)
    assert await coordinator.get('same',lambda: 'recovered')=='recovered'


@pytest.mark.asyncio
async def test_cancelled_queued_preview_never_starts():
    coordinator=PreviewCoordinator()
    await coordinator.limit.acquire()
    await coordinator.limit.acquire()
    calls=[]
    task=asyncio.create_task(coordinator.get('obsolete',lambda: calls.append(1)))
    await asyncio.sleep(0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    coordinator.limit.release()
    coordinator.limit.release()
    await asyncio.sleep(0)
    assert calls==[]
