"""Bounded exact-integer checks for compact v0.2 evidence."""

from itertools import product
from math import isqrt


# These are every prime congruent to 3 modulo 4 below 32.
_TWO_SQUARE_OBSTRUCTION_PRIMES = (3, 7, 11, 19, 23, 31)
_PCM16_MAGNITUDE_MAX = 1 << 15
_PCM16_SQUARE_MAX = _PCM16_MAGNITUDE_MAX ** 2


def _sum_of_two_squares_residues_possible(power: int) -> bool:
    """Apply bounded necessary conditions, not a general factorization proof.

    A sum of two integer squares has odd part 1 modulo 4. Every prime that
    is 3 modulo 4 must also have even valuation. Check the fixed small-prime
    set without trial division up to sqrt(power), which would be unbounded
    for identity-bearing FFT integers. Full coefficients remain sidecar data.
    """
    if power < 0:
        return False
    if power == 0:
        return True
    odd_part = power >> ((power & -power).bit_length() - 1)
    if odd_part % 4 != 1:
        return False
    for prime in _TWO_SQUARE_OBSTRUCTION_PRIMES:
        odd_exponent = False
        while odd_part % prime == 0:
            odd_part //= prime
            odd_exponent = not odd_exponent
        if odd_exponent:
            return False
    return True


def _pcm16_signs(magnitude: int) -> tuple[int, ...]:
    if magnitude == 0:
        return (0,)
    if magnitude == _PCM16_MAGNITUDE_MAX:
        return (-magnitude,)
    return (-magnitude, magnitude)


def _three_sample_vectors(energy: int, windowed_energy: int) -> list[tuple[int, int, int]]:
    """Enumerate PCM16 triples with both source and 1,2,3-window energies.

    Subtraction gives W-E = 3*y^2 + 8*z^2. Enumerate at most 32769 z
    magnitudes, then derive y^2 and x^2 exactly. This avoids a quadratic
    scan of all PCM16 coordinate pairs and preserves the -32768 endpoint.
    """
    if not 0 <= energy <= 3 * _PCM16_SQUARE_MAX:
        return []
    if not energy <= windowed_energy <= 9 * energy:
        return []
    if windowed_energy > 14 * _PCM16_SQUARE_MAX:
        return []
    difference = windowed_energy - energy
    limit = min(_PCM16_MAGNITUDE_MAX, isqrt(energy), isqrt(difference // 8))
    vectors: list[tuple[int, int, int]] = []
    for third in range(limit + 1):
        second_square, remainder = divmod(difference - 8 * third * third, 3)
        if remainder or second_square > _PCM16_SQUARE_MAX:
            continue
        first_square = energy - second_square - third * third
        if not 0 <= first_square <= _PCM16_SQUARE_MAX:
            continue
        first = isqrt(first_square)
        second = isqrt(second_square)
        if first * first != first_square or second * second != second_square:
            continue
        vectors.extend(product(_pcm16_signs(first), _pcm16_signs(second), _pcm16_signs(third)))
    return vectors


def _joint_vectors_match_gram(gram: list[list[int]], candidates: list[list[tuple[int, ...]]]) -> bool:
    """Find one assignment satisfying every dot product, not separate pairs."""
    if any(not domain for domain in candidates):
        return False
    order = sorted(range(len(candidates)), key=lambda index: len(candidates[index]))
    assigned: dict[int, tuple[int, ...]] = {}

    def search(position: int) -> bool:
        if position == len(order):
            return True
        index = order[position]
        for vector in candidates[index]:
            if any(
                sum(left * right for left, right in zip(vector, other)) != gram[index][other_index]
                for other_index, other in assigned.items()
            ):
                continue
            assigned[index] = vector
            if search(position + 1):
                return True
            del assigned[index]
        return False

    return search(0)
