"""Strict PCM16 RIFF/WAVE input adapter for the QSOL-MAP reference profile."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import struct
from typing import Tuple


class WavFormatError(ValueError):
    """Raised when an input cannot be interpreted by the frozen WAV adapter."""


@dataclass(frozen=True)
class PCM16Wave:
    source_sha256: str
    pcm_s16le_sha256: str
    sample_rate_hz: int
    channels: int
    frame_count: int
    samples_by_channel: Tuple[Tuple[int, ...], ...]


def parse_pcm16_wav(blob: bytes) -> PCM16Wave:
    if len(blob) < 12:
        raise WavFormatError("truncated RIFF header")
    if blob[0:4] != b"RIFF" or blob[8:12] != b"WAVE":
        raise WavFormatError("only little-endian RIFF/WAVE is supported")

    riff_size = struct.unpack_from("<I", blob, 4)[0]
    if riff_size + 8 != len(blob):
        raise WavFormatError("RIFF size must match the complete source byte length")

    fmt = None
    data = None
    offset = 12
    while offset < len(blob):
        if offset + 8 > len(blob):
            raise WavFormatError("truncated RIFF chunk header")
        chunk_id = blob[offset : offset + 4]
        chunk_size = struct.unpack_from("<I", blob, offset + 4)[0]
        body_start = offset + 8
        body_end = body_start + chunk_size
        if body_end > len(blob):
            raise WavFormatError("RIFF chunk extends beyond file boundary")
        body = blob[body_start:body_end]

        if chunk_id == b"fmt ":
            if fmt is not None:
                raise WavFormatError("duplicate fmt chunk")
            fmt = body
        elif chunk_id == b"data":
            if data is not None:
                raise WavFormatError("duplicate data chunk")
            data = body

        offset = body_end + (chunk_size & 1)
        if offset > len(blob):
            raise WavFormatError("missing RIFF padding byte")

    if offset != len(blob):
        raise WavFormatError("invalid RIFF chunk alignment")
    if fmt is None or data is None:
        raise WavFormatError("both fmt and data chunks are required")
    if len(fmt) != 16:
        raise WavFormatError("fmt chunk must use the exact 16-byte PCM form; extensions are unsupported")

    audio_format, channels, sample_rate, byte_rate, block_align, bits_per_sample = (
        struct.unpack_from("<HHIIHH", fmt, 0)
    )
    if audio_format != 1:
        raise WavFormatError("only uncompressed integer PCM (format 1) is supported")
    if not 1 <= channels <= 8:
        raise WavFormatError("channel count must be between 1 and 8")
    if not 1 <= sample_rate <= 768_000:
        raise WavFormatError("sample rate is outside the reference adapter bounds")
    if bits_per_sample != 16:
        raise WavFormatError("only signed PCM16 is supported")
    expected_block_align = channels * 2
    if block_align != expected_block_align:
        raise WavFormatError("block alignment does not match PCM16 channel count")
    if byte_rate != sample_rate * expected_block_align:
        raise WavFormatError("byte rate does not match sample rate and block alignment")
    if len(data) == 0:
        raise WavFormatError("empty PCM payload")
    if len(data) % block_align:
        raise WavFormatError("PCM payload is not an integer number of frames")

    flat = tuple(sample for (sample,) in struct.iter_unpack("<h", data))
    frame_count = len(flat) // channels
    by_channel = tuple(
        tuple(flat[index::channels])
        for index in range(channels)
    )

    return PCM16Wave(
        source_sha256=hashlib.sha256(blob).hexdigest(),
        pcm_s16le_sha256=hashlib.sha256(data).hexdigest(),
        sample_rate_hz=sample_rate,
        channels=channels,
        frame_count=frame_count,
        samples_by_channel=by_channel,
    )
