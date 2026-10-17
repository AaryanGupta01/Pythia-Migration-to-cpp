"""Discrete-event simulation of a multi-server queue (M/M/c style) driven by a priority queue of events."""
from __future__ import annotations

import heapq
import logging
from dataclasses import dataclass, field
from typing import List

from quanta.util.rng import Lcg

log = logging.getLogger(__name__)

ARRIVAL, DEPARTURE = 0, 1


@dataclass(order=True)
class Event:
    time: float
    kind: int = field(compare=False)
    customer: int = field(compare=False)


@dataclass
class QueueStats:
    served: int
    mean_wait: float
    max_queue: int
    utilisation: float


def exponential(rng: Lcg, rate: float) -> float:
    """Exponentially distributed waiting time with the given rate (inverse-transform sampling)."""
    u = rng.next_float()
    # -ln(1 - u) by the atanh series: ln(1 - u) = -2 * atanh(u / (2 - u))
    z = u / (2.0 - u)
    series, term = 0.0, z
    for k in range(1, 40, 2):
        series += term / k
        term *= z * z
    return 2.0 * series / rate


def simulate_queue(customers: int, servers: int, arrival_rate: float, service_rate: float, seed: int) -> QueueStats:
    """Simulate `customers` arrivals at `servers` identical servers with a single FIFO line."""
    rng = Lcg(seed)
    events: List[Event] = []
    clock = 0.0
    for c in range(customers):
        clock += exponential(rng, arrival_rate)
        heapq.heappush(events, Event(clock, ARRIVAL, c))
    free = servers
    waiting: List[tuple] = []
    total_wait, served, max_queue, busy_time = 0.0, 0, 0, 0.0
    last = 0.0
    while events:
        ev = heapq.heappop(events)
        busy_time += (servers - free) * (ev.time - last)
        last = ev.time
        if ev.kind == ARRIVAL:
            if free > 0:
                free -= 1
                served += 1
                heapq.heappush(events, Event(ev.time + exponential(rng, service_rate), DEPARTURE, ev.customer))
            else:
                waiting.append((ev.time, ev.customer))
                max_queue = max(max_queue, len(waiting))
        else:
            if waiting:
                arrived, who = waiting.pop(0)
                total_wait += ev.time - arrived
                served += 1
                heapq.heappush(events, Event(ev.time + exponential(rng, service_rate), DEPARTURE, who))
            else:
                free += 1
    log.debug("queue: %d served, makespan %.2f", served, last)
    return QueueStats(served, total_wait / max(1, served), max_queue, busy_time / (servers * last) if last else 0.0)
