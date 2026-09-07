"""Necessary overlap constraints for exact short/long tail energies."""

from __future__ import annotations

from math import isqrt


_PCM16_MAGNITUDE_MAX = 1 << 15
_EXACT_RESIDUAL_ENERGY_LIMIT = 1 << 16


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


def _small_residual_energy_is_realizable(
    residual: int, weights: tuple[int, ...]
) -> bool:
    """Exactly solve bounded residual weighted-square feasibility.

    For a small residual, only weights whose square is no larger than the
    residual can contribute. A bitset dynamic program chooses at most one
    squared PCM magnitude per source position. Residuals above the fixed bound
    retain the surrounding necessary non-negativity check rather than turning
    compact verification into an unbounded subset-sum search.
    """
    if residual < 0:
        return False
    if residual == 0:
        return True
    if not weights:
        return False
    if residual > _EXACT_RESIDUAL_ENERGY_LIMIT:
        return True

    mask = (1 << (residual + 1)) - 1
    reachable = 1
    root_residual = isqrt(residual)
    for weight in weights:
        magnitude_limit = min(_PCM16_MAGNITUDE_MAX, root_residual // weight)
        if magnitude_limit == 0:
            continue
        previous = reachable
        updated = previous
        weight_square = weight * weight
        for magnitude in range(1, magnitude_limit + 1):
            contribution = weight_square * magnitude * magnitude
            updated |= previous << contribution
        reachable = updated & mask
        if (reachable >> residual) & 1:
            return True
    return False


def _tail_energy_fits_previous_overlap(
    previous_energy: int,
    current_energy: int,
    current_available: int,
    previous_overlap_weights: tuple[int, ...],
    previous_nonoverlap_weights: tuple[int, ...] = (),
) -> bool:
    """Require one exact current-tail witness to fit the previous frame energy.

    Consecutive short and long frames overlap by exactly half a symmetric
    triangular window. When the later frame has only one or two real source
    samples, its exact energy determines a bounded set of squared sample
    magnitudes. Those same samples occur in the preceding frame at the supplied
    overlap weights. For each witness, the remaining previous-frame energy
    must be nonnegative and, for small residuals, exactly realizable by the
    preceding non-overlap weights.

    If callers omit ``previous_nonoverlap_weights``, the frozen triangular
    half-window is recovered from the first overlap weight: short and long
    adjacent frames begin their overlap at weights 128 and 512 respectively,
    so the preceding non-overlap weights are exactly 1..that value.

    This is a necessary compact-envelope check. Large residuals deliberately
    remain a bounded necessary test; full sidecar verification reconstructs
    the complete waveform.
    """
    if current_available not in (1, 2):
        return True
    if len(previous_overlap_weights) != current_available:
        return False
    if not previous_nonoverlap_weights:
        if not previous_overlap_weights or previous_overlap_weights[0] <= 0:
            return False
        previous_nonoverlap_weights = tuple(
            range(1, previous_overlap_weights[0] + 1)
        )

    options = _tail_squared_magnitude_options(current_energy, current_available)
    if not options:
        return False
    for squares in options:
        overlap_contribution = sum(
            square * weight * weight
            for square, weight in zip(squares, previous_overlap_weights)
        )
        residual = previous_energy - overlap_contribution
        if _small_residual_energy_is_realizable(
            residual, previous_nonoverlap_weights
        ):
            return True
    return False
