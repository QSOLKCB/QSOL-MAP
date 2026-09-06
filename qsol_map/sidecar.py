"""Streaming full-spectral sidecar for QSOL-MAP v0.2."""

from __future__ import annotations

import hashlib
import hmac
import json
from typing import Iterable, TextIO

from .analysis import _fixed_fft_real, _windowed_frame
from .canonical import canonical_bytes, domain_sha256
from .multiresolution import (
    LONG_COMPLEX_MATRIX_DOMAIN,
    LONG_POWER_MATRIX_DOMAIN,
    LONG_PROFILE_ID,
    V01_PROFILE_ID,
    _fixed_fft_long,
    _hex_digest,
    _plain_int,
    _signed_decimal,
    _unsigned_decimal,
    _windowed_long_frame,
    verify_multiresolution_envelope,
)
from .tables import FRAME_SIZE, HOP_SIZE
from .v02_tables import LONG_FRAME_SIZE, LONG_HOP_SIZE, LONG_TOP_K
from .wav import PCM16Wave

SIDECAR_SCHEMA = "qsol-map-spectral-sidecar-v0.2"
SIDECAR_HEADER_DOMAIN = "QSOL-MAP/SIDECAR-HEADER/v0.2"
SIDECAR_RECORDS_DOMAIN = "QSOL-MAP/SIDECAR-RECORDS/v0.2"
SIDECAR_RECEIPT_DOMAIN = "QSOL-MAP/SIDECAR-RECEIPT/v0.2"
SHORT_COMPLEX_MATRIX_DOMAIN = "QSOL-MAP/COMPLEX-MATRIX/v0.1"
SHORT_POWER_MATRIX_DOMAIN = "QSOL-MAP/POWER-MATRIX/v0.1"
MAX_SIDECAR_LINE_CHARS = 4_000_000


def _matrix_hasher(domain: str) -> "hashlib._Hash":
    hasher = hashlib.sha256()
    hasher.update(domain.encode("utf-8") + b"\x00")
    return hasher


def _update_matrix_hash(hasher: "hashlib._Hash", row: object) -> None:
    encoded = canonical_bytes(row)
    hasher.update(len(encoded).to_bytes(8, "big"))
    hasher.update(encoded)


def _update_records_hash(hasher: "hashlib._Hash", record: dict) -> None:
    encoded = canonical_bytes(record)
    hasher.update(len(encoded).to_bytes(8, "big"))
    hasher.update(encoded)


def _header(wave: PCM16Wave, envelope: dict) -> dict:
    return {
        "record_type": "header",
        "schema": SIDECAR_SCHEMA,
        "percept_sha256": envelope["percept_sha256"],
        "source": envelope["percept"]["source"],
        "profiles": [
            {
                "id": V01_PROFILE_ID,
                "frame_size_samples": FRAME_SIZE,
                "hop_size_samples": HOP_SIZE,
                "bin_count": FRAME_SIZE // 2 + 1,
            },
            {
                "id": LONG_PROFILE_ID,
                "frame_size_samples": LONG_FRAME_SIZE,
                "hop_size_samples": LONG_HOP_SIZE,
                "bin_count": LONG_FRAME_SIZE // 2 + 1,
            },
        ],
    }


def _frame_record(profile_id: str, channel_index: int, frame_index: int, start: int, coefficients) -> dict:
    return {
        "record_type": "spectral_frame",
        "profile_id": profile_id,
        "channel_index": channel_index,
        "frame_index": frame_index,
        "sample_start": start,
        "coefficients": [
            [str(real), str(imag), str(real * real + imag * imag)]
            for real, imag in coefficients
        ],
    }


def _write_record(stream: TextIO, record: dict) -> None:
    stream.write(canonical_bytes(record).decode("utf-8"))
    stream.write("\n")


def write_spectral_sidecar(wave: PCM16Wave, envelope: dict, stream: TextIO) -> dict:
    """Write deterministic canonical-NDJSON spectral evidence with bounded row memory."""
    if not verify_multiresolution_envelope(envelope):
        raise ValueError("sidecar requires a valid v0.2 percept envelope")
    source = envelope["percept"]["source"]
    if source["wav_sha256"] != wave.source_sha256 or source["pcm_s16le_sha256"] != wave.pcm_s16le_sha256:
        raise ValueError("sidecar source does not match percept source")
    if source["sample_rate_hz"] != wave.sample_rate_hz or source["channels"] != wave.channels or source["frame_count"] != wave.frame_count:
        raise ValueError("sidecar source metadata does not match percept source")

    header = _header(wave, envelope)
    _write_record(stream, header)
    header_sha256 = domain_sha256(SIDECAR_HEADER_DOMAIN, canonical_bytes(header))

    records_hash = _matrix_hasher(SIDECAR_RECORDS_DOMAIN)
    record_count = 0

    for channel_index, samples in enumerate(wave.samples_by_channel):
        for frame_index, start in enumerate(range(0, len(samples), HOP_SIZE)):
            coefficients = _fixed_fft_real(_windowed_frame(samples, start))
            record = _frame_record(V01_PROFILE_ID, channel_index, frame_index, start, coefficients)
            _write_record(stream, record)
            _update_records_hash(records_hash, record)
            record_count += 1

    for channel_index, samples in enumerate(wave.samples_by_channel):
        for frame_index, start in enumerate(range(0, len(samples), LONG_HOP_SIZE)):
            coefficients = _fixed_fft_long(_windowed_long_frame(samples, start))
            record = _frame_record(LONG_PROFILE_ID, channel_index, frame_index, start, coefficients)
            _write_record(stream, record)
            _update_records_hash(records_hash, record)
            record_count += 1

    records_sha256 = records_hash.hexdigest()
    receipt_core = {
        "header_sha256": header_sha256,
        "records_sha256": records_sha256,
        "record_count": record_count,
    }
    receipt_sha256 = domain_sha256(SIDECAR_RECEIPT_DOMAIN, canonical_bytes(receipt_core))
    trailer = {
        "record_type": "trailer",
        **receipt_core,
        "receipt_sha256": receipt_sha256,
    }
    _write_record(stream, trailer)
    return trailer


def _canonical_line(line: str) -> dict | None:
    if len(line) > MAX_SIDECAR_LINE_CHARS or not line.endswith("\n"):
        return None
    raw = line[:-1]
    try:
        value = json.loads(raw)
        if not isinstance(value, dict):
            return None
        if canonical_bytes(value).decode("utf-8") != raw:
            return None
    except (json.JSONDecodeError, TypeError, ValueError, UnicodeError, RecursionError):
        return None
    return value


def _expected_sequence(envelope: dict):
    frame_count = envelope["percept"]["source"]["frame_count"]
    channel_count = envelope["percept"]["source"]["channels"]
    short_count = (frame_count + HOP_SIZE - 1) // HOP_SIZE
    long_count = (frame_count + LONG_HOP_SIZE - 1) // LONG_HOP_SIZE
    for channel_index in range(channel_count):
        for frame_index in range(short_count):
            yield V01_PROFILE_ID, channel_index, frame_index, frame_index * HOP_SIZE
    for channel_index in range(channel_count):
        for frame_index in range(long_count):
            yield LONG_PROFILE_ID, channel_index, frame_index, frame_index * LONG_HOP_SIZE


def verify_spectral_sidecar(envelope: dict, lines: Iterable[str]) -> bool:
    """Verify sidecar framing, row arithmetic, hashes, ordering and compact commitments."""
    if not verify_multiresolution_envelope(envelope):
        return False
    iterator = iter(lines)
    try:
        first_line = next(iterator)
    except StopIteration:
        return False
    header = _canonical_line(first_line)
    expected_header = {
        "record_type": "header",
        "schema": SIDECAR_SCHEMA,
        "percept_sha256": envelope["percept_sha256"],
        "source": envelope["percept"]["source"],
        "profiles": [
            {"id": V01_PROFILE_ID, "frame_size_samples": FRAME_SIZE, "hop_size_samples": HOP_SIZE, "bin_count": FRAME_SIZE // 2 + 1},
            {"id": LONG_PROFILE_ID, "frame_size_samples": LONG_FRAME_SIZE, "hop_size_samples": LONG_HOP_SIZE, "bin_count": LONG_FRAME_SIZE // 2 + 1},
        ],
    }
    if header is None:
        return False
    try:
        if canonical_bytes(header) != canonical_bytes(expected_header):
            return False
    except (TypeError, ValueError, UnicodeError, RecursionError):
        return False
    header_sha256 = domain_sha256(SIDECAR_HEADER_DOMAIN, canonical_bytes(header))

    channel_count = envelope["percept"]["source"]["channels"]
    long_channels = envelope["percept"]["channels"]
    short_complex = [_matrix_hasher(SHORT_COMPLEX_MATRIX_DOMAIN) for _ in range(channel_count)]
    short_power = [_matrix_hasher(SHORT_POWER_MATRIX_DOMAIN) for _ in range(channel_count)]
    long_complex = [_matrix_hasher(LONG_COMPLEX_MATRIX_DOMAIN) for _ in range(channel_count)]
    long_power = [_matrix_hasher(LONG_POWER_MATRIX_DOMAIN) for _ in range(channel_count)]
    long_aggregate = [
        [0] * (LONG_FRAME_SIZE // 2 + 1)
        for _ in range(channel_count)
    ]
    records_hash = _matrix_hasher(SIDECAR_RECORDS_DOMAIN)

    record_count = 0
    for profile_id, channel_index, frame_index, sample_start in _expected_sequence(envelope):
        try:
            line = next(iterator)
        except StopIteration:
            return False
        record = _canonical_line(line)
        if record is None or set(record) != {
            "record_type", "profile_id", "channel_index", "frame_index", "sample_start", "coefficients"
        }:
            return False
        if record["record_type"] != "spectral_frame" or record["profile_id"] != profile_id:
            return False
        if not _plain_int(record["channel_index"]) or not _plain_int(record["frame_index"]) or not _plain_int(record["sample_start"]):
            return False
        if record["channel_index"] != channel_index or record["frame_index"] != frame_index or record["sample_start"] != sample_start:
            return False

        coefficients = record["coefficients"]
        expected_bins = FRAME_SIZE // 2 + 1 if profile_id == V01_PROFILE_ID else LONG_FRAME_SIZE // 2 + 1
        if not isinstance(coefficients, list) or len(coefficients) != expected_bins:
            return False
        complex_row = []
        power_row = []
        power_values = []
        for bin_index, item in enumerate(coefficients):
            if not isinstance(item, list) or len(item) != 3:
                return False
            if not _signed_decimal(item[0]) or not _signed_decimal(item[1]) or not _unsigned_decimal(item[2]):
                return False
            try:
                real = int(item[0])
                imag = int(item[1])
                power = int(item[2])
            except (TypeError, ValueError):
                return False
            if bin_index in (0, expected_bins - 1) and imag != 0:
                return False
            if real * real + imag * imag != power:
                return False
            complex_row.append([item[0], item[1]])
            power_row.append(item[2])
            power_values.append(power)

        if profile_id == V01_PROFILE_ID:
            _update_matrix_hash(short_complex[channel_index], complex_row)
            _update_matrix_hash(short_power[channel_index], power_row)
        else:
            event = long_channels[channel_index]["long_spectral"]["events"][frame_index]
            centroid_denominator = sum(power_values)
            centroid_numerator = sum(
                bin_index * power for bin_index, power in enumerate(power_values)
            )
            ranked = sorted(
                range(expected_bins),
                key=lambda bin_index: (-power_values[bin_index], bin_index),
            )[:LONG_TOP_K]
            dominant_non_dc = max(
                range(1, expected_bins),
                key=lambda bin_index: (power_values[bin_index], -bin_index),
            )
            expected_components = [
                {
                    "bin": bin_index,
                    "real": coefficients[bin_index][0],
                    "imag": coefficients[bin_index][1],
                    "power": coefficients[bin_index][2],
                }
                for bin_index in ranked
            ]
            if event["spectral_centroid_bin"] != {
                "numerator": str(centroid_numerator),
                "denominator": str(centroid_denominator),
            }:
                return False
            if event["dominant_non_dc_bin"] != dominant_non_dc:
                return False
            if event["top_components"] != expected_components:
                return False

            _update_matrix_hash(long_complex[channel_index], complex_row)
            _update_matrix_hash(long_power[channel_index], power_row)
            for bin_index, power in enumerate(power_values):
                long_aggregate[channel_index][bin_index] += power
        _update_records_hash(records_hash, record)
        record_count += 1

    try:
        trailer_line = next(iterator)
    except StopIteration:
        return False
    trailer = _canonical_line(trailer_line)
    if trailer is None or set(trailer) != {"record_type", "header_sha256", "records_sha256", "record_count", "receipt_sha256"}:
        return False
    if trailer["record_type"] != "trailer":
        return False
    if not _plain_int(trailer["record_count"]) or trailer["record_count"] != record_count:
        return False
    if not _hex_digest(trailer["header_sha256"]) or not _hex_digest(trailer["records_sha256"]) or not _hex_digest(trailer["receipt_sha256"]):
        return False
    if trailer["header_sha256"] != header_sha256 or trailer["records_sha256"] != records_hash.hexdigest():
        return False
    receipt_core = {
        "header_sha256": trailer["header_sha256"],
        "records_sha256": trailer["records_sha256"],
        "record_count": trailer["record_count"],
    }
    expected_receipt = domain_sha256(SIDECAR_RECEIPT_DOMAIN, canonical_bytes(receipt_core))
    if not hmac.compare_digest(expected_receipt, trailer["receipt_sha256"]):
        return False
    try:
        next(iterator)
        return False
    except StopIteration:
        pass

    short_commitments = envelope["percept"]["short_reference"]["channels"]
    for channel_index in range(channel_count):
        if short_complex[channel_index].hexdigest() != short_commitments[channel_index]["complex_matrix_sha256"]:
            return False
        if short_power[channel_index].hexdigest() != short_commitments[channel_index]["power_matrix_sha256"]:
            return False
        if long_complex[channel_index].hexdigest() != long_channels[channel_index]["long_spectral"]["complex_matrix_sha256"]:
            return False
        if long_power[channel_index].hexdigest() != long_channels[channel_index]["long_spectral"]["power_matrix_sha256"]:
            return False
        reported_aggregate = long_channels[channel_index]["long_spectral"]["aggregate_power_by_bin"]
        if reported_aggregate != [str(value) for value in long_aggregate[channel_index]]:
            return False
    return True