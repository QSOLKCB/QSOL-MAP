"""QSOL-MAP v0.2 verifier surface with latest compact hardening."""

from __future__ import annotations

from collections import deque
from math import gcd, isqrt

from . import multiresolution_base as _base


# Preserve the established public/private surface. The base module contains the
# frozen transform implementation and the accumulated v0.2 verifier. This thin
# layer adds review-derived necessary constraints without duplicating that code.
for _name in dir(_base):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_base, _name)

_BASE_VALIDATOR = _base._validate_percept_core
_SCALE_SQUARED = _LONG_FFT_ENDPOINT_SCALE * _LONG_FFT_ENDPOINT_SCALE
_PCM16_MIN = -(1 << 15)
_PCM16_MAX = (1 << 15) - 1


def _scaled_divisor(divisor: int, factor: int) -> int:
    """Return a guaranteed divisor after multiplying a component by a factor."""
    if divisor == 0 or factor == 0:
        return 0
    return divisor * abs(factor)


def _compute_long_bin_component_divisors() -> tuple[tuple[int, ...], tuple[int, ...]]:
    """Propagate guaranteed integer divisors through the frozen long FFT.

    Each bit-reversed input real component starts as one arbitrary integer and
    each imaginary component starts identically zero. For every butterfly we
    propagate the gcd of the divisors of the integer terms being added or
    subtracted. The result is a precomputable necessary divisor for every real
    and imaginary output coefficient. It follows the committed twiddle table
    and stage schedule directly, so special bins are not hard-coded.
    """
    state = [(1, 0) for _ in range(LONG_FRAME_SIZE)]
    width = 2
    while width <= LONG_FRAME_SIZE:
        half = width // 2
        twiddle_step = LONG_FRAME_SIZE // width
        for base in range(0, LONG_FRAME_SIZE, width):
            for offset in range(half):
                twiddle_index = offset * twiddle_step
                wr = TWIDDLE_COS_Q15_1024[twiddle_index]
                wi = TWIDDLE_SIN_Q15_1024[twiddle_index]
                ur, ui = state[base + offset]
                vr, vi = state[base + offset + half]

                tr = gcd(_scaled_divisor(vr, wr), _scaled_divisor(vi, wi))
                ti = gcd(_scaled_divisor(vr, wi), _scaled_divisor(vi, wr))
                out_real = gcd(_scaled_divisor(ur, Q15_ONE), tr)
                out_imag = gcd(_scaled_divisor(ui, Q15_ONE), ti)
                state[base + offset] = (out_real, out_imag)
                state[base + offset + half] = (out_real, out_imag)
        width *= 2

    retained = state[: LONG_FRAME_SIZE // 2 + 1]
    return (
        tuple(real for real, _ in retained),
        tuple(imag for _, imag in retained),
    )


_LONG_BIN_REAL_DIVISORS, _LONG_BIN_IMAG_DIVISORS = (
    _compute_long_bin_component_divisors()
)


def _transform_divisibility_is_valid(channel: dict) -> bool:
    """Apply frozen-transform divisibility to every event and aggregate bin."""
    spectral = channel["long_spectral"]
    aggregate = spectral["aggregate_power_by_bin"]

    # Every event coefficient at a given bin has the same guaranteed component
    # divisors. Consequently every individual power, and therefore the sum of
    # those powers in the aggregate row, has the corresponding gcd divisor.
    for bin_index, encoded_power in enumerate(aggregate):
        power = _core._safe_decimal_int(encoded_power)
        if power is None:
            return False
        real_divisor = _LONG_BIN_REAL_DIVISORS[bin_index]
        imag_divisor = _LONG_BIN_IMAG_DIVISORS[bin_index]
        power_divisor = gcd(real_divisor * real_divisor, imag_divisor * imag_divisor)
        if power_divisor:
            if power % power_divisor:
                return False
        elif power != 0:
            return False

    for event in spectral["events"]:
        for component in event["top_components"]:
            bin_index = component["bin"]
            real = _core._safe_decimal_int(component["real"], signed=True)
            imag = _core._safe_decimal_int(component["imag"], signed=True)
            if real is None or imag is None:
                return False
            real_divisor = _LONG_BIN_REAL_DIVISORS[bin_index]
            imag_divisor = _LONG_BIN_IMAG_DIVISORS[bin_index]
            if (real_divisor == 0 and real != 0) or (
                real_divisor != 0 and real % real_divisor
            ):
                return False
            if (imag_divisor == 0 and imag != 0) or (
                imag_divisor != 0 and imag % imag_divisor
            ):
                return False
    return True


def _endpoint_signed_options(event: dict, endpoint: int, magnitude: int) -> tuple[int, ...] | None:
    """Return scaled signed endpoint values allowed by compact evidence."""
    component = next(
        (item for item in event["top_components"] if item["bin"] == endpoint),
        None,
    )
    if component is None:
        return (0,) if magnitude == 0 else (-magnitude, magnitude)
    real = _core._safe_decimal_int(component["real"], signed=True)
    imag = _core._safe_decimal_int(component["imag"], signed=True)
    if real is None or imag != 0 or real % _LONG_FFT_ENDPOINT_SCALE:
        return None
    signed = real // _LONG_FFT_ENDPOINT_SCALE
    if abs(signed) != magnitude:
        return None
    return (signed,)


def _single_event_endpoint_energy_bounds_are_valid(
    channel: dict, frame_count: int
) -> bool:
    """Apply Cauchy bounds and exact equality witnesses to endpoint evidence."""
    spectral = channel["long_spectral"]
    events = spectral["events"]
    if len(events) != 1:
        return True
    event = events[0]
    energy = _core._safe_decimal_int(event["windowed_energy"])
    if energy is None:
        return False
    available = min(
        LONG_FRAME_SIZE,
        max(0, frame_count - event["sample_start"]),
    )
    if available <= 0:
        return False

    endpoints = (0, LONG_FRAME_SIZE // 2)
    magnitudes: dict[int, int] = {}
    signed_options: dict[int, tuple[int, ...]] = {}
    equality_endpoints: list[int] = []
    for endpoint in endpoints:
        power = _core._safe_decimal_int(spectral["aggregate_power_by_bin"][endpoint])
        if power is None:
            return False
        root = isqrt(power)
        magnitude, remainder = divmod(root, _LONG_FFT_ENDPOINT_SCALE)
        if root * root != power or remainder:
            return False
        if magnitude * magnitude > available * energy:
            return False
        options = _endpoint_signed_options(event, endpoint, magnitude)
        if options is None:
            return False
        magnitudes[endpoint] = magnitude
        signed_options[endpoint] = options
        if magnitude * magnitude == available * energy:
            equality_endpoints.append(endpoint)

    if not equality_endpoints:
        return True

    # Equality in |sum a_i|^2 <= A*sum(a_i^2) forces all a_i to be
    # identical. For Nyquist the same statement applies after multiplying by
    # (-1)^i. One equality endpoint therefore fixes the complete windowed
    # vector; validate that vector against triangular-weight divisibility,
    # PCM16 range, energy, and the other endpoint observation as well.
    forcing_endpoint = equality_endpoints[0]
    candidates: list[tuple[int, ...]] = []
    for signed_endpoint in signed_options[forcing_endpoint]:
        if signed_endpoint % available:
            continue
        constant = signed_endpoint // available
        samples: list[int] = []
        valid = True
        for index in range(available):
            windowed_value = constant
            if forcing_endpoint != 0 and index % 2:
                windowed_value = -windowed_value
            weight = LONG_WINDOW_WEIGHTS[index]
            if windowed_value % weight:
                valid = False
                break
            sample = windowed_value // weight
            if not _PCM16_MIN <= sample <= _PCM16_MAX:
                valid = False
                break
            samples.append(sample)
        if valid:
            candidates.append(tuple(samples))

    for samples in candidates:
        windowed = [
            LONG_WINDOW_WEIGHTS[index] * sample
            for index, sample in enumerate(samples)
        ]
        if sum(value * value for value in windowed) != energy:
            continue
        actual = {
            0: sum(windowed),
            LONG_FRAME_SIZE // 2: sum(
                value if index % 2 == 0 else -value
                for index, value in enumerate(windowed)
            ),
        }
        if all(
            abs(actual[endpoint]) == magnitudes[endpoint]
            and actual[endpoint] in signed_options[endpoint]
            for endpoint in endpoints
        ):
            return True
    return False


def _two_sample_endpoint_candidates(channel: dict) -> list[tuple[int, int]]:
    """Recover PCM16 two-sample witnesses compatible with signed endpoints."""
    spectral = channel["long_spectral"]
    events = spectral["events"]
    if len(events) != 1:
        return []
    event = events[0]
    energy = _core._safe_decimal_int(event["windowed_energy"])
    if energy is None:
        return []

    endpoints = (0, LONG_FRAME_SIZE // 2)
    options: list[tuple[int, ...]] = []
    for endpoint in endpoints:
        power = _core._safe_decimal_int(spectral["aggregate_power_by_bin"][endpoint])
        if power is None:
            return []
        root = isqrt(power)
        magnitude, remainder = divmod(root, _LONG_FFT_ENDPOINT_SCALE)
        if root * root != power or remainder:
            return []
        signed = _endpoint_signed_options(event, endpoint, magnitude)
        if signed is None:
            return []
        options.append(signed)

    candidates: set[tuple[int, int]] = set()
    for dc in options[0]:
        for nyquist in options[1]:
            first_numerator = dc + nyquist
            second_numerator = dc - nyquist
            if first_numerator % 2 or second_numerator % 4:
                continue
            first = first_numerator // 2
            second = second_numerator // 4
            if not (
                _PCM16_MIN <= first <= _PCM16_MAX
                and _PCM16_MIN <= second <= _PCM16_MAX
            ):
                continue
            if first * first + 4 * second * second != energy:
                continue
            candidates.add((first, second))
    return sorted(candidates)


def _two_sample_endpoint_witnesses_are_valid(percept: dict) -> bool:
    """Bind two-sample endpoint signs, long energy and Gram data jointly."""
    if percept["source"]["frame_count"] != 2:
        return True

    candidates = [
        _two_sample_endpoint_candidates(channel) for channel in percept["channels"]
    ]
    if any(not channel_candidates for channel_candidates in candidates):
        return False
    if percept["source"]["channels"] == 1:
        return True

    gram = _base._relationship_gram_matrix(percept)
    if gram is None:
        return False
    for channel_index, channel_candidates in enumerate(candidates):
        candidates[channel_index] = [
            vector
            for vector in channel_candidates
            if vector[0] * vector[0] + vector[1] * vector[1]
            == gram[channel_index][channel_index]
        ]
        if not candidates[channel_index]:
            return False

    order = sorted(range(len(candidates)), key=lambda index: len(candidates[index]))
    assigned: dict[int, tuple[int, int]] = {}

    def search(position: int) -> bool:
        if position == len(order):
            return True
        channel_index = order[position]
        for vector in candidates[channel_index]:
            if any(
                vector[0] * other[0] + vector[1] * other[1]
                != gram[channel_index][other_index]
                for other_index, other in assigned.items()
            ):
                continue
            assigned[channel_index] = vector
            if search(position + 1):
                return True
            del assigned[channel_index]
        return False

    return search(0)


def _aggregate_residual_allocation_is_feasible(channel: dict) -> bool:
    """Require one joint event/bin allocation for all omitted spectral power."""
    spectral = channel["long_spectral"]
    aggregate: list[int] = []
    for value in spectral["aggregate_power_by_bin"]:
        parsed = _core._safe_decimal_int(value)
        if parsed is None:
            return False
        aggregate.append(parsed)

    events = spectral["events"]
    selected_by_bin = [0] * len(aggregate)
    row_residuals: list[int] = []
    event_caps: list[tuple[dict[int, int], int, int]] = []
    for event in events:
        selected: dict[int, int] = {}
        selected_total = 0
        for component in event["top_components"]:
            power = _core._safe_decimal_int(component["power"])
            if power is None:
                return False
            selected[component["bin"]] = power
            selected_total += power
            selected_by_bin[component["bin"]] += power
        if not event["top_components"]:
            return False
        weakest = event["top_components"][-1]
        weakest_power = _core._safe_decimal_int(weakest["power"])
        if weakest_power is None:
            return False
        denominator = _core._safe_decimal_int(
            event["spectral_centroid_bin"]["denominator"]
        )
        if denominator is None or denominator < selected_total:
            return False
        row_residuals.append(denominator - selected_total)
        event_caps.append((selected, weakest["bin"], weakest_power))

    column_residuals = [
        aggregate_power - selected_power
        for aggregate_power, selected_power in zip(aggregate, selected_by_bin)
    ]
    if any(value < 0 for value in column_residuals):
        return False
    total_residual = sum(row_residuals)
    if total_residual != sum(column_residuals):
        return False
    if total_residual == 0:
        return True

    positive_bins = [
        bin_index for bin_index, residual in enumerate(column_residuals) if residual
    ]
    positive_events = [
        event_index for event_index, residual in enumerate(row_residuals) if residual
    ]

    source = 0
    event_offset = 1
    bin_offset = event_offset + len(positive_events)
    sink = bin_offset + len(positive_bins)
    graph: list[list[list[int]]] = [[] for _ in range(sink + 1)]

    def add_edge(left: int, right: int, capacity: int) -> None:
        forward = [right, len(graph[right]), capacity]
        reverse = [left, len(graph[left]), 0]
        graph[left].append(forward)
        graph[right].append(reverse)

    event_node: dict[int, int] = {}
    for position, event_index in enumerate(positive_events):
        node = event_offset + position
        event_node[event_index] = node
        add_edge(source, node, row_residuals[event_index])

    bin_node: dict[int, int] = {}
    for position, bin_index in enumerate(positive_bins):
        node = bin_offset + position
        bin_node[bin_index] = node
        add_edge(node, sink, column_residuals[bin_index])

    for event_index in positive_events:
        selected, weakest_bin, weakest_power = event_caps[event_index]
        for bin_index in positive_bins:
            if bin_index in selected:
                continue
            allowance = weakest_power - (1 if bin_index < weakest_bin else 0)
            if allowance <= 0:
                continue
            capacity = min(
                allowance,
                row_residuals[event_index],
                column_residuals[bin_index],
            )
            if capacity:
                add_edge(event_node[event_index], bin_node[bin_index], capacity)

    flow = 0
    while flow < total_residual:
        level = [-1] * len(graph)
        level[source] = 0
        queue = deque([source])
        while queue:
            node = queue.popleft()
            for target, _, capacity in graph[node]:
                if capacity > 0 and level[target] < 0:
                    level[target] = level[node] + 1
                    queue.append(target)
        if level[sink] < 0:
            break
        next_edge = [0] * len(graph)

        def push(node: int, amount: int) -> int:
            if node == sink:
                return amount
            while next_edge[node] < len(graph[node]):
                edge = graph[node][next_edge[node]]
                target, reverse_index, capacity = edge
                if capacity > 0 and level[target] == level[node] + 1:
                    sent = push(target, min(amount, capacity))
                    if sent:
                        edge[2] -= sent
                        graph[target][reverse_index][2] += sent
                        return sent
                next_edge[node] += 1
            return 0

        while flow < total_residual:
            sent = push(source, total_residual - flow)
            if not sent:
                break
            flow += sent

    return flow == total_residual


def _long_energy_covers_relationship_energy(percept: dict) -> bool:
    """Require long-event weighted energies to cover full-source channel energy."""
    if percept["source"]["channels"] <= 1:
        return True
    source_energies = _base._relationship_channel_energies(percept)
    if source_energies is None:
        return False
    for channel_index, channel in enumerate(percept["channels"]):
        total = 0
        for event in channel["long_spectral"]["events"]:
            energy = _core._safe_decimal_int(event["windowed_energy"])
            if energy is None:
                return False
            total += energy
        if total < source_energies[channel_index]:
            return False
    return True


def _zero_long_energy_forces_zero_transient(percept: dict) -> bool:
    """Couple the exact all-zero long state to the short transient summary."""
    for channel in percept["channels"]:
        long_energies: list[int] = []
        for event in channel["long_spectral"]["events"]:
            energy = _core._safe_decimal_int(event["windowed_energy"])
            if energy is None:
                return False
            long_energies.append(energy)
        if not long_energies or any(long_energies):
            continue

        transient = channel["transient"]
        positive_sum = _core._safe_decimal_int(transient["positive_delta_sum"])
        maximum = _core._safe_decimal_int(transient["maximum_positive_delta"])
        if positive_sum is None or maximum is None:
            return False
        if (
            transient["candidate_count"] != 0
            or transient["strongest_candidates"]
            or positive_sum != 0
            or maximum != 0
        ):
            return False
    return True


def _one_sample_relationship_signs_match_endpoints(percept: dict) -> bool:
    """Bind one-sample relationship dots to the signed endpoint-derived PCM."""
    if percept["source"]["frame_count"] != 1:
        return True

    samples: list[int] = []
    for channel in percept["channels"]:
        event = channel["long_spectral"]["events"][0]
        dc = next(
            (item for item in event["top_components"] if item["bin"] == 0),
            None,
        )
        if dc is None:
            return False
        real = _core._safe_decimal_int(dc["real"], signed=True)
        imag = _core._safe_decimal_int(dc["imag"], signed=True)
        if (
            real is None
            or imag != 0
            or real % _LONG_FFT_ENDPOINT_SCALE
        ):
            return False
        samples.append(real // _LONG_FFT_ENDPOINT_SCALE)

    for relation in percept["channel_relationships"]:
        left = relation["left_channel"]
        right = relation["right_channel"]
        dot = _core._safe_decimal_int(relation["dot_product"], signed=True)
        if dot is None or dot != samples[left] * samples[right]:
            return False
    return True


def _reported_transient_energy_state(
    transient: dict,
) -> tuple[dict[int, int], set[int]] | None:
    """Collect short-frame energies fixed by the reported candidate records."""
    known_energy: dict[int, int] = {}
    reported_frames: set[int] = set()
    for candidate in transient["strongest_candidates"]:
        frame = candidate["frame_index"]
        previous = _core._safe_decimal_int(candidate["previous_energy"])
        current = _core._safe_decimal_int(candidate["current_energy"])
        if previous is None or current is None:
            return None
        reported_frames.add(frame)
        for energy_frame, value in ((frame - 1, previous), (frame, current)):
            existing = known_energy.get(energy_frame)
            if existing is not None and existing != value:
                return None
            known_energy[energy_frame] = value
    return known_energy, reported_frames


def _short_energy_is_source_feasible(
    frame_count: int, energy_frame: int, energy: int
) -> bool:
    """Check one short-frame energy against source bounds and exact tiny tails."""
    if energy < 0:
        return False
    if energy > _base._short_frame_energy_bound(frame_count, energy_frame):
        return False
    available = min(
        SHORT_FRAME_SIZE,
        max(0, frame_count - energy_frame * SHORT_HOP_SIZE),
    )
    return _base._small_window_energy_is_realizable(energy, available)


def _noncandidate_positive_delta_bound(frame_count: int, frame_index: int) -> int:
    """Return a necessary maximum delta for a transition that is not a candidate."""
    previous_max = _base._short_frame_energy_bound(frame_count, frame_index - 1)
    current_max = _base._short_frame_energy_bound(frame_count, frame_index)
    if previous_max <= 0 or current_max <= 0:
        return 0
    return min((previous_max - 1) // 2, (current_max - 1) // 3)


def _maximum_noncandidate_delta_from_known_energies(
    frame_count: int,
    frame_index: int,
    known_energy: dict[int, int],
) -> int:
    """Upper-bound one non-candidate positive delta using fixed neighbors."""
    previous = known_energy.get(frame_index - 1)
    current = known_energy.get(frame_index)
    if previous is not None and current is not None:
        delta = current - previous
        return delta if delta > 0 and 2 * current < 3 * previous else 0
    if previous is not None:
        current_max = _base._short_frame_energy_bound(frame_count, frame_index)
        return max(0, min(current_max - previous, (previous - 1) // 2))
    if current is not None:
        if current <= 0:
            return 0
        previous_max = _base._short_frame_energy_bound(frame_count, frame_index - 1)
        minimum_previous = (2 * current) // 3 + 1
        if minimum_previous > min(previous_max, current - 1):
            return 0
        return current - minimum_previous
    return _noncandidate_positive_delta_bound(frame_count, frame_index)


def _transition_can_realize_noncandidate_delta(
    frame_count: int,
    frame_index: int,
    delta: int,
    known_energy: dict[int, int],
) -> bool:
    """Honor reported neighboring energies when placing a non-candidate rise."""
    if delta <= 0:
        return False
    previous = known_energy.get(frame_index - 1)
    current = known_energy.get(frame_index)

    if previous is not None and current is not None:
        return (
            current - previous == delta
            and current > previous
            and 2 * current < 3 * previous
        )
    if previous is not None:
        current = previous + delta
        return (
            _short_energy_is_source_feasible(frame_count, frame_index, current)
            and 2 * current < 3 * previous
        )
    if current is not None:
        previous = current - delta
        return (
            _short_energy_is_source_feasible(frame_count, frame_index - 1, previous)
            and current > previous
            and 2 * current < 3 * previous
        )
    return _noncandidate_positive_delta_bound(frame_count, frame_index) >= delta


def _minimum_candidate_delta_from_known_energies(
    frame_count: int,
    frame_index: int,
    known_energy: dict[int, int],
) -> int | None:
    """Return a necessary omitted-candidate delta from any reported neighbors."""
    previous = known_energy.get(frame_index - 1)
    current = known_energy.get(frame_index)

    if previous is not None and current is not None:
        if current <= previous or 2 * current < 3 * previous:
            return None
        return current - previous
    if previous is not None:
        minimum = max(1, (previous + 1) // 2)
        if previous + minimum > _base._short_frame_energy_bound(
            frame_count, frame_index
        ):
            return None
        return minimum
    if current is not None:
        if current <= 0:
            return None
        previous_cap = min(
            _base._short_frame_energy_bound(frame_count, frame_index - 1),
            current - 1,
            (2 * current) // 3,
        )
        if previous_cap < 0:
            return None
        return current - previous_cap
    return 1


def _maximum_candidate_delta_from_known_energies(
    frame_count: int,
    frame_index: int,
    known_energy: dict[int, int],
) -> int | None:
    """Upper-bound an omitted candidate delta using fixed neighboring energies."""
    previous = known_energy.get(frame_index - 1)
    current = known_energy.get(frame_index)
    minimum = _minimum_candidate_delta_from_known_energies(
        frame_count, frame_index, known_energy
    )
    if minimum is None:
        return None
    if previous is not None and current is not None:
        return current - previous
    if previous is not None:
        maximum = _base._short_frame_energy_bound(frame_count, frame_index) - previous
        return maximum if maximum >= minimum else None
    if current is not None:
        return current if current >= minimum else None
    maximum = _base._short_frame_energy_bound(frame_count, frame_index)
    return maximum if maximum >= minimum else None


def _transient_noncandidate_maximum_is_feasible(percept: dict) -> bool:
    frame_count = percept["source"]["frame_count"]
    short_event_count = (
        frame_count + SHORT_HOP_SIZE - 1
    ) // SHORT_HOP_SIZE
    transition_count = max(0, short_event_count - 1)

    for channel in percept["channels"]:
        transient = channel["transient"]
        maximum = _core._safe_decimal_int(transient["maximum_positive_delta"])
        if maximum is None:
            return False
        reported = transient["strongest_candidates"]
        strongest_reported = 0
        if reported:
            strongest_reported = _core._safe_decimal_int(
                reported[0]["positive_delta"]
            )
            if strongest_reported is None:
                return False

        if maximum <= strongest_reported:
            continue
        noncandidate_count = transition_count - transient["candidate_count"]
        if noncandidate_count <= 0:
            return False

        state = _reported_transient_energy_state(transient)
        if state is None:
            return False
        known_energy, reported_frames = state
        if not any(
            frame_index not in reported_frames
            and _transition_can_realize_noncandidate_delta(
                frame_count, frame_index, maximum, known_energy
            )
            for frame_index in range(1, transition_count + 1)
        ):
            return False
    return True


def _transient_unreported_mass_is_feasible(percept: dict) -> bool:
    """Upper-bound total unreported positive mass under exact classifications."""
    frame_count = percept["source"]["frame_count"]
    short_event_count = (
        frame_count + SHORT_HOP_SIZE - 1
    ) // SHORT_HOP_SIZE
    transition_count = max(0, short_event_count - 1)

    for channel in percept["channels"]:
        transient = channel["transient"]
        state = _reported_transient_energy_state(transient)
        if state is None:
            return False
        known_energy, reported_frames = state
        reported = transient["strongest_candidates"]
        reported_deltas = [
            _core._safe_decimal_int(item["positive_delta"]) for item in reported
        ]
        positive_sum = _core._safe_decimal_int(transient["positive_delta_sum"])
        if positive_sum is None or any(delta is None for delta in reported_deltas):
            return False
        reported_sum = sum(delta for delta in reported_deltas if delta is not None)
        unreported_mass = positive_sum - reported_sum
        if unreported_mass < 0:
            return False

        omitted_count = transient["candidate_count"] - len(reported)
        if omitted_count < 0:
            return False
        unreported_frames = [
            frame for frame in range(1, transition_count + 1)
            if frame not in reported_frames
        ]
        if omitted_count > len(unreported_frames):
            return False

        baseline = 0
        candidate_gains: list[int] = []
        weakest_delta = weakest_frame = None
        if omitted_count:
            if not reported:
                return False
            weakest_delta = _core._safe_decimal_int(reported[-1]["positive_delta"])
            weakest_frame = reported[-1]["frame_index"]
            if weakest_delta is None:
                return False

        for frame in unreported_frames:
            noncandidate_cap = _maximum_noncandidate_delta_from_known_energies(
                frame_count, frame, known_energy
            )
            baseline += noncandidate_cap
            if not omitted_count:
                continue
            minimum = _minimum_candidate_delta_from_known_energies(
                frame_count, frame, known_energy
            )
            candidate_cap = _maximum_candidate_delta_from_known_energies(
                frame_count, frame, known_energy
            )
            allowance = weakest_delta - (1 if frame < weakest_frame else 0)
            if minimum is None or candidate_cap is None or allowance < minimum:
                continue
            candidate_cap = min(candidate_cap, allowance)
            if candidate_cap >= minimum:
                candidate_gains.append(candidate_cap - noncandidate_cap)

        if len(candidate_gains) < omitted_count:
            return False
        candidate_gains.sort(reverse=True)
        maximum_unreported_mass = baseline + sum(candidate_gains[:omitted_count])
        if unreported_mass > maximum_unreported_mass:
            return False
    return True


def _omitted_candidate_adjacency_is_feasible(percept: dict) -> bool:
    """Use reported neighboring energies to place omitted candidates exactly."""
    frame_count = percept["source"]["frame_count"]
    short_event_count = (
        frame_count + SHORT_HOP_SIZE - 1
    ) // SHORT_HOP_SIZE
    transition_count = max(0, short_event_count - 1)

    for channel in percept["channels"]:
        transient = channel["transient"]
        reported = transient["strongest_candidates"]
        omitted_count = transient["candidate_count"] - len(reported)
        if omitted_count <= 0:
            continue
        if not reported:
            return False

        state = _reported_transient_energy_state(transient)
        if state is None:
            return False
        known_energy, reported_frames = state
        unreported_frames = [
            frame for frame in range(1, transition_count + 1)
            if frame not in reported_frames
        ]
        if len(unreported_frames) < omitted_count:
            return False

        weakest_delta = _core._safe_decimal_int(reported[-1]["positive_delta"])
        weakest_frame = reported[-1]["frame_index"]
        positive_sum = _core._safe_decimal_int(transient["positive_delta_sum"])
        reported_deltas = [
            _core._safe_decimal_int(item["positive_delta"])
            for item in reported
        ]
        if (
            weakest_delta is None
            or positive_sum is None
            or any(delta is None for delta in reported_deltas)
        ):
            return False
        reported_sum = sum(delta for delta in reported_deltas if delta is not None)
        unreported_mass = positive_sum - reported_sum
        if unreported_mass < 0:
            return False

        eligible_minima: list[int] = []
        for frame in unreported_frames:
            allowance = weakest_delta - (1 if frame < weakest_frame else 0)
            minimum = _minimum_candidate_delta_from_known_energies(
                frame_count, frame, known_energy
            )
            if minimum is not None and 1 <= minimum <= allowance:
                eligible_minima.append(minimum)

        # Mixed candidate/non-candidate sets still have to contain enough
        # unreported frames that can actually be the claimed omitted candidates.
        if len(eligible_minima) < omitted_count:
            return False
        if sum(sorted(eligible_minima)[:omitted_count]) > unreported_mass:
            return False
    return True


def _validate_percept_core(percept: object) -> bool:
    """Run the accumulated verifier plus the latest necessary constraints."""
    if not _BASE_VALIDATOR(percept):
        return False

    frame_count = percept["source"]["frame_count"]
    for channel in percept["channels"]:
        if not _transform_divisibility_is_valid(channel):
            return False
        if not _single_event_endpoint_energy_bounds_are_valid(channel, frame_count):
            return False
        if not _aggregate_residual_allocation_is_feasible(channel):
            return False
    if not _two_sample_endpoint_witnesses_are_valid(percept):
        return False
    if not _long_energy_covers_relationship_energy(percept):
        return False
    if not _zero_long_energy_forces_zero_transient(percept):
        return False
    if not _one_sample_relationship_signs_match_endpoints(percept):
        return False
    if not _transient_noncandidate_maximum_is_feasible(percept):
        return False
    if not _transient_unreported_mass_is_feasible(percept):
        return False
    if not _omitted_candidate_adjacency_is_feasible(percept):
        return False
    return True


# Public verification resolves this core hook at call time. The base module is
# intentionally left intact so reloads keep a stable validator underneath this
# thin hardening layer.
_core._validate_percept_core = _validate_percept_core