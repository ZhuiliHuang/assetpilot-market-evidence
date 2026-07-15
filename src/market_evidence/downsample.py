"""Deterministic chart downsampling that preserves decision-relevant points."""

from __future__ import annotations

from typing import Any


def downsample_points(
    points: list[dict[str, Any]],
    *,
    max_points: int = 360,
    reference_bands: tuple[float, ...] = (20.0, 50.0, 80.0),
) -> list[dict[str, Any]]:
    if max_points < 2:
        raise ValueError("max_points must be at least two")
    if len(points) <= max_points:
        return list(points)

    keep = {0, len(points) - 1}
    for index, point in enumerate(points):
        if point.get("value") is None:
            keep.add(index)
        if index == 0:
            continue
        previous = points[index - 1].get("value")
        current = point.get("value")
        if previous is None or current is None:
            continue
        for band in reference_bands:
            if (previous < band <= current) or (current <= band < previous):
                keep.update({index - 1, index})

    for index in range(1, len(points) - 1):
        previous = points[index - 1].get("value")
        current = points[index].get("value")
        following = points[index + 1].get("value")
        if previous is None or current is None or following is None:
            continue
        if (current > previous and current > following) or (
            current < previous and current < following
        ):
            keep.add(index)

    remaining = max_points - len(keep)
    if remaining > 0:
        step = max(1, (len(points) - 2) // remaining)
        keep.update(range(1, len(points) - 1, step))

    if len(keep) > max_points:
        interior = sorted(keep - {0, len(points) - 1})
        slots = max_points - 2
        stride = max(1, len(interior) // max(slots, 1))
        keep = {0, len(points) - 1, *interior[::stride][:slots]}

    return [points[index] for index in sorted(keep)]
