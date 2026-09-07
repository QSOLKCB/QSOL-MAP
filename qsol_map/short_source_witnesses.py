"""Exact, bounded PCM16 witnesses for complete three/four-sample sources.

These functions check specified energies/endpoints and a joint Gram assignment.
They do not verify unreported spectral coefficients or source commitments.
"""

from math import isqrt

PCM16_MIN = -(1 << 15)
PCM16_MAX = (1 << 15) - 1


def short_source_vectors(
    sample_count: int,
    source_energy: int,
    windowed_energy: int,
    dc_values: tuple[int, ...],
    nyquist_values: tuple[int, ...],
) -> list[tuple[int, ...]]:
    """Enumerate every endpoint-compatible three/four-sample PCM16 witness.

    With weights (1,2,3,4), A=(D+N)/2=x+3z and B=(D-N)/4=y+2t.
    For each bounded t (t=0 for three samples), derive y, then solve
    (x-3z)^2 = 2*(W-4y^2-16t^2)-A^2. There are at most four endpoint
    sign pairs, 65536 t values per pair, and two square-root signs per t.
    The signed PCM16 bounds are asymmetric; +32768 is never a witness.
    """
    if sample_count not in (3, 4):
        return []
    if not 0 <= source_energy <= sample_count * (1 << 30):
        return []
    weight_square_sum = 14 if sample_count == 3 else 30
    if not 0 <= windowed_energy <= weight_square_sum * (1 << 30):
        return []
    if not dc_values or not nyquist_values:
        return []

    fourth_limit = min(1 << 15, isqrt(source_energy), isqrt(windowed_energy // 16))
    fourth_values = (
        range(max(PCM16_MIN, -fourth_limit), min(PCM16_MAX, fourth_limit) + 1)
        if sample_count == 4 else (0,)
    )
    witnesses: set[tuple[int, ...]] = set()
    for dc in dc_values:
        for nyquist in nyquist_values:
            if (dc + nyquist) % 2 or (dc - nyquist) % 4:
                continue
            even_sum = (dc + nyquist) // 2
            odd_sum = (dc - nyquist) // 4
            for fourth in fourth_values:
                second = odd_sum - 2 * fourth
                if not PCM16_MIN <= second <= PCM16_MAX:
                    continue
                second_square = second * second
                fourth_square = fourth * fourth
                if second_square + fourth_square > source_energy:
                    continue
                even_energy = windowed_energy - 4 * second_square - 16 * fourth_square
                discriminant = 2 * even_energy - even_sum * even_sum
                if discriminant < 0:
                    continue
                root = isqrt(discriminant)
                if root * root != discriminant:
                    continue
                for signed_root in ((0,) if root == 0 else (-root, root)):
                    if (even_sum + signed_root) % 2 or (even_sum - signed_root) % 6:
                        continue
                    first = (even_sum + signed_root) // 2
                    third = (even_sum - signed_root) // 6
                    if not (
                        PCM16_MIN <= first <= PCM16_MAX
                        and PCM16_MIN <= third <= PCM16_MAX
                    ):
                        continue
                    vector = (first, second, third)
                    if sample_count == 4:
                        vector += (fourth,)
                    if sum(value * value for value in vector) != source_energy:
                        continue
                    if sum(
                        ((index + 1) * value) ** 2
                        for index, value in enumerate(vector)
                    ) != windowed_energy:
                        continue
                    witnesses.add(vector)
    return sorted(witnesses)


def vectors_have_joint_gram(
    candidates: list[list[tuple[int, ...]]], gram: list[list[int]]
) -> bool:
    """Require one shared candidate assignment, not separate pairwise witnesses."""
    count = len(candidates)
    if not count or len(gram) != count or any(len(row) != count for row in gram):
        return False
    if any(not vectors for vectors in candidates):
        return False
    order = sorted(range(count), key=lambda index: len(candidates[index]))
    assigned: dict[int, tuple[int, ...]] = {}

    def search(position: int) -> bool:
        if position == count:
            return True
        channel = order[position]
        for vector in candidates[channel]:
            if sum(value * value for value in vector) != gram[channel][channel]:
                continue
            if any(
                len(vector) != len(other)
                or sum(left * right for left, right in zip(vector, other))
                != gram[channel][other_channel]
                for other_channel, other in assigned.items()
            ):
                continue
            assigned[channel] = vector
            if search(position + 1):
                return True
            del assigned[channel]
        return False

    return search(0)
