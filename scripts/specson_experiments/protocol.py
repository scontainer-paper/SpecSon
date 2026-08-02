from __future__ import annotations

import statistics
import time
from dataclasses import dataclass
from typing import Callable, Generic, TypeVar


T = TypeVar("T")


@dataclass(frozen=True)
class TimedSample(Generic[T]):
    elapsed_ms: float
    observation: T


@dataclass(frozen=True)
class PairedResult(Generic[T]):
    specson: tuple[TimedSample[T], ...]
    jsonb: tuple[TimedSample[T], ...]
    discard_first: int

    def retained(self, system: str) -> tuple[TimedSample[T], ...]:
        samples = self.specson if system == "specson" else self.jsonb
        return samples[self.discard_first :]

    def median_ms(self, system: str) -> float:
        return statistics.median(sample.elapsed_ms for sample in self.retained(system))

    def as_dict(self) -> dict:
        specson_median = self.median_ms("specson")
        jsonb_median = self.median_ms("jsonb")
        return {
            "rounds": len(self.specson),
            "discard_first": self.discard_first,
            "specson_all_ms": [sample.elapsed_ms for sample in self.specson],
            "jsonb_all_ms": [sample.elapsed_ms for sample in self.jsonb],
            "specson_retained_ms": [
                sample.elapsed_ms for sample in self.retained("specson")
            ],
            "jsonb_retained_ms": [sample.elapsed_ms for sample in self.retained("jsonb")],
            "specson_median_ms": specson_median,
            "jsonb_median_ms": jsonb_median,
            "speedup": jsonb_median / specson_median,
            "specson_observations": [sample.observation for sample in self.specson],
            "jsonb_observations": [sample.observation for sample in self.jsonb],
        }


def timed(call: Callable[[], T]) -> TimedSample[T]:
    started = time.perf_counter_ns()
    observation = call()
    elapsed_ms = (time.perf_counter_ns() - started) / 1_000_000.0
    return TimedSample(elapsed_ms=elapsed_ms, observation=observation)


def paired_rounds(
    specson: Callable[[], T],
    jsonb: Callable[[], T],
    *,
    rounds: int = 10,
    discard_first: int = 5,
    before: Callable[[str], None] | None = None,
    after: Callable[[str], None] | None = None,
) -> PairedResult[T]:
    if rounds <= discard_first:
        raise ValueError("formal rounds must exceed discarded rounds")
    samples: dict[str, list[TimedSample[T]]] = {"specson": [], "jsonb": []}
    calls = {"specson": specson, "jsonb": jsonb}
    for ordinal in range(rounds):
        order = ("specson", "jsonb") if ordinal % 2 == 0 else ("jsonb", "specson")
        for system in order:
            if before is not None:
                before(system)
            samples[system].append(timed(calls[system]))
            if after is not None:
                after(system)
    return PairedResult(
        specson=tuple(samples["specson"]),
        jsonb=tuple(samples["jsonb"]),
        discard_first=discard_first,
    )
