"""
Background refresh loop.

Rather than one blunt interval, series are refreshed on a cadence matched to
how often they can actually change. Checking quarterly GDP every 15 minutes
spends API calls to learn nothing.

Note the interaction with the two-tier cache: even when a tier is due, the
client still short-circuits on FRED's `last_updated`, so a "due" monthly series
that has not been revised costs one small metadata call, not a full download.
"""

from __future__ import annotations

import asyncio
import logging

from .indicators import ALL_INDICATORS, Freq
from .service import MacroService

log = logging.getLogger(__name__)

# seconds between refresh sweeps, per declared frequency
INTERVALS: dict[Freq, int] = {
    Freq.DAILY: 30 * 60,
    Freq.WEEKLY: 2 * 3600,
    Freq.MONTHLY: 6 * 3600,
    Freq.QUARTERLY: 12 * 3600,
}


async def _loop(svc: MacroService, freq: Freq, interval: int) -> None:
    members = [i for i in ALL_INDICATORS if i.freq is freq]
    if not members:
        return
    while True:
        try:
            errors = await svc.client.ensure_many(members)
            if errors:
                log.warning("%s sweep: %d errors: %s", freq.value, len(errors), errors)
            else:
                log.info("%s sweep complete (%d series)", freq.value, len(members))
            svc.invalidate()
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001
            # A scheduler loop must never die -- log and keep going.
            log.exception("Scheduler sweep failed for %s", freq.value)
        await asyncio.sleep(interval)


def start(svc: MacroService) -> list[asyncio.Task]:
    tasks = []
    for freq, interval in INTERVALS.items():
        t = asyncio.create_task(_loop(svc, freq, interval), name=f"refresh-{freq.value}")
        tasks.append(t)
    log.info("Started %d refresh loops", len(tasks))
    return tasks


async def stop(tasks: list[asyncio.Task]) -> None:
    for t in tasks:
        t.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
