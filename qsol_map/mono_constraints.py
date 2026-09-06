"""Bounded PCM16 feasibility for a single three-sample long window."""

from itertools import product
from math import isqrt


_PCM16_MAGNITUDE_MAX = 1 << 15


def _three_sample_window_vectors(
    energy: int, dc_magnitude: int, nyquist_magnitude: int
) -> list[tuple[int, int, int]]:
    """Recover PCM16 triples matching weighted energy and endpoint magnitudes.

    After removing the exact FFT scale, signed endpoints are
    D = x + 2*y + 3*z and N = x - 2*y + 3*z. For each of their
    four possible sign pairs, y = (D-N)/4 and A = (D+N)/2 = x+3*z.
    Then (x-3*z)^2 = 2*(energy-4*y^2)-A^2 determines x and z,
    with at most two roots. No search over PCM16 coordinates is needed.
    This checks these three observations, not the complete spectrum.
    """
    if not 0 <= energy <= 14 * _PCM16_MAGNITUDE_MAX ** 2:
        return []
    if not all(
        0 <= value <= 6 * _PCM16_MAGNITUDE_MAX
        for value in (dc_magnitude, nyquist_magnitude)
    ):
        return []

    vectors: set[tuple[int, int, int]] = set()
    dc_values = (0,) if dc_magnitude == 0 else (-dc_magnitude, dc_magnitude)
    nyquist_values = (
        (0,) if nyquist_magnitude == 0 else (-nyquist_magnitude, nyquist_magnitude)
    )
    for dc, nyquist in product(dc_values, nyquist_values):
        second, remainder = divmod(dc - nyquist, 4)
        if remainder or not -32768 <= second <= 32767:
            continue
        outer_sum = (dc + nyquist) // 2
        discriminant = 2 * (energy - 4 * second * second) - outer_sum * outer_sum
        if discriminant < 0:
            continue
        root = isqrt(discriminant)
        if root * root != discriminant:
            continue
        for difference in ((0,) if root == 0 else (-root, root)):
            first, first_remainder = divmod(outer_sum + difference, 2)
            third, third_remainder = divmod(outer_sum - difference, 6)
            if first_remainder or third_remainder:
                continue
            if -32768 <= first <= 32767 and -32768 <= third <= 32767:
                vectors.add((first, second, third))
    return sorted(vectors)
