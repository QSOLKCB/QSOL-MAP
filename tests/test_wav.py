import struct
import unittest

from qsol_map.wav import WavFormatError, parse_pcm16_wav


def make_wav(samples, sample_rate=48000, channels=1, fmt_extra=b""):
    payload = struct.pack("<" + "h" * len(samples), *samples)
    block_align = channels * 2
    fmt = struct.pack(
        "<HHIIHH",
        1,
        channels,
        sample_rate,
        sample_rate * block_align,
        block_align,
        16,
    ) + fmt_extra
    fmt_chunk = b"fmt " + struct.pack("<I", len(fmt)) + fmt
    if len(fmt) & 1:
        fmt_chunk += b"\x00"
    body = fmt_chunk
    body += b"data" + struct.pack("<I", len(payload)) + payload
    return b"RIFF" + struct.pack("<I", 4 + len(body)) + b"WAVE" + body


class WavTests(unittest.TestCase):
    def test_parse_mono(self):
        wave = parse_pcm16_wav(make_wav([0, 1, -2, 32767, -32768]))
        self.assertEqual(wave.sample_rate_hz, 48000)
        self.assertEqual(wave.channels, 1)
        self.assertEqual(wave.frame_count, 5)
        self.assertEqual(wave.samples_by_channel[0][-1], -32768)

    def test_parse_stereo_deinterleaves_without_downmix(self):
        wave = parse_pcm16_wav(make_wav([1, 10, 2, 20, 3, 30], channels=2))
        self.assertEqual(wave.samples_by_channel, ((1, 2, 3), (10, 20, 30)))

    def test_reject_non_pcm16(self):
        blob = bytearray(make_wav([0, 1]))
        struct.pack_into("<H", blob, 34, 8)
        with self.assertRaises(WavFormatError):
            parse_pcm16_wav(bytes(blob))

    def test_reject_riff_size_mismatch(self):
        with self.assertRaises(WavFormatError):
            parse_pcm16_wav(make_wav([1, 2, 3]) + b"x")

    def test_reject_odd_sized_extended_fmt_chunk(self):
        with self.assertRaises(WavFormatError):
            parse_pcm16_wav(make_wav([1, 2, 3], fmt_extra=b"\x00"))

    def test_reject_pcm_fmt_extension_even_when_cbsize_is_zero(self):
        with self.assertRaises(WavFormatError):
            parse_pcm16_wav(make_wav([1, 2, 3], fmt_extra=struct.pack("<H", 0)))


if __name__ == "__main__":
    unittest.main()
