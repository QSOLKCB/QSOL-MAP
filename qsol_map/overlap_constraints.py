"""Necessary overlap constraints for exact short/long tail energies."""

from __future__ import annotations

from math import isqrt


_PCM16_MAGNITUDE_MAX = 1 << 15


def _tail_squared_magnitude_options(
    energy: int, available: int
) -> list[tuple[int, ...]]:
    """Return squared sample magnitudes for exact one/two-sample tail energy."""
    if energy < 0:
        return []
    if available == 1:
        root = isqrt(energy)
        if root > _PCM16_MAGNITUDE_MAX or root * root != energy:
            return []
        return [(energy,)]
    if available == 2:
        options: set[tuple[int, int]] = set()
        limit = min(_PCM16_MAGNITUDE_MAX, isqrt(energy // 4))
        for second in range(limit + 1):
            first_square = energy - 4 * second * second
            first = isqrt(first_square)
            if first <= _PCM16_MAGNITUDE_MAX and first * first == first_square:
                options.add((first_square, second * second))
        return sorted(options)
    return []


def _tail_energy_fits_previous_overlap(
    previous_energy: int,
    current_energy: int,
    current_available: int,
    previous_overlap_weights: tuple[int, ...],
) -> bool:
    """Require one exact current-tail witness to fit the previous frame energy.

    Consecutive short and long frames overlap by exactly half a window. When
    the later frame has only one or two real source samples, its exact energy
    determines a bounded set of squared sample magnitudes. Those same samples
    occur in the preceding frame at the supplied overlap weights, so their
    contribution cannot exceed that preceding frame's declared energy.

    This is a necessary compact-envelope check. It does not claim to solve the
    remaining non-overlap energy realization for a longer preceding frame.
    """
    if current_available not in (1, 2):
        return True
    if len(previous_overlap_weights) != current_available:
        return False
    options = _tail_squared_magnitude_options(current_energy, current_available)
    if not options:
        return False
    return any(
        sum(
            square * weight * weight
            for square, weight in zip(squares, previous_overlap_weights)
        )
        <= previous_energy
        for squares in options
    )
