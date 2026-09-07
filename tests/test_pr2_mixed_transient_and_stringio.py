"""Regressions for mixed transient gaps and StringIO verification newlines."""

import copy
import io
import unittest

from qsol_map import multiresolution as mr
from qsol_map import sidecar
from qsol_map.wav import parse_pcm16_wav
from test_pr2_live_review_fixes import make_wav, rehash


class MixedTransientEvidenceTests(unittest.TestCase):
    def _mixed_candidate_fixture(self):
        # 2432 source frames produce 19 short events / 18 transitions, with a
        # 128-sample final short tail so unrelated one/two-sample overlap rules
        # do not constrain this synthetic energy chain. Frames 5 and 10 are
        # plateaus; all other transitions are exact 2x rises and candidates.
        # Their reported neighbors bind both plateau deltas to zero even though
        # those two transition records are omitted.
        changed = copy.deepcopy(
            mr.build_multiresolution_percept(
                parse_pcm16_wav(make_wav([1] + [0] * 2431))
            )
        )
        energies = [1]
        for frame in range(1, 19):
            energies.append(
                energies[-1] if frame in (5, 10) else 2 * energies[-1]
            )

        candidates = []
        for frame in range(1, 19):
            if frame in (5, 10):
                self.assertEqual(energies[frame], energies[frame - 1])
                continue
            previous = energies[frame - 1]
            current = energies[frame]
            delta = current - previous
            candidates.append(
                {
                    "frame_index": frame,
                    "sample_start": frame * mr.SHORT_HOP_SIZE,
                    "previous_energy": str(previous),
                    "current_energy": str(current),
                    "positive_delta": str(delta),
                    "rise_ratio": {
                        "numerator": str(current),
                        "denominator": str(previous),
                    },
                }
            )
        candidates.sort(
            key=lambda item: (-int(item["positive_delta"]), item["frame_index"])
        )
        self.assertEqual(len(candidates), 16)

        transient = changed["percept"]["channels"][0]["transient"]
        reported_sum = sum(int(item["positive_delta"]) for item in candidates)
        strongest = int(candidates[0]["positive_delta"])
        transient.update(
            {
                "candidate_count": 16,
                "positive_delta_sum": str(reported_sum),
                "maximum_positive_delta": str(strongest),
                "strongest_candidates": candidates,
            }
        )
        rehash(changed)
        self.assertTrue(mr.verify_multiresolution_envelope(changed))
        return changed, reported_sum, strongest

    def test_mixed_candidate_set_cannot_assign_candidate_to_fixed_zero_gap(self):
        changed, reported_sum, _ = self._mixed_candidate_fixture()
        transient = changed["percept"]["channels"][0]["transient"]

        # Claim one of the two unreported plateau transitions is a seventeenth
        # candidate and give it the minimum positive mass. Both gaps are fixed
        # to delta zero by neighboring reported candidate energies.
        transient["candidate_count"] = 17
        transient["positive_delta_sum"] = str(reported_sum + 1)
        rehash(changed)
        self.assertFalse(mr.verify_multiresolution_envelope(changed))

    def test_noncandidate_maximum_cannot_use_fixed_zero_gap(self):
        changed, reported_sum, strongest = self._mixed_candidate_fixture()
        transient = changed["percept"]["channels"][0]["transient"]
        forged_maximum = 40000
        self.assertGreater(forged_maximum, strongest)

        # Both unreported transitions have exact delta zero from their reported
        # neighbors, so neither can provide this purported non-candidate rise.
        transient["positive_delta_sum"] = str(reported_sum + forged_maximum)
        transient["maximum_positive_delta"] = str(forged_maximum)
        rehash(changed)
        self.assertFalse(mr.verify_multiresolution_envelope(changed))


class StringIOVerificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.wave = parse_pcm16_wav(make_wav([1, 0, 0, 0]))
        cls.envelope = mr.build_multiresolution_percept(cls.wave)
        destination = io.StringIO(newline="\n")
        sidecar.write_spectral_sidecar(cls.wave, cls.envelope, destination)
        cls.text = destination.getvalue()

    def test_newline_translating_stringio_input_is_rejected(self):
        translated = io.StringIO(
            self.text.replace("\n", "\r\n"),
            newline=None,
        )
        # The constructor has already erased the noncanonical CRLF evidence.
        self.assertNotIn("\r", translated.getvalue())
        self.assertEqual(translated.getvalue(), self.text)
        self.assertFalse(sidecar.verify_spectral_sidecar(self.envelope, translated))

        # Explicit modes that do not translate input remain valid verifier
        # sources for canonical LF-only sidecars.
        self.assertTrue(
            sidecar.verify_spectral_sidecar(
                self.envelope, io.StringIO(self.text, newline="\n")
            )
        )
        self.assertTrue(
            sidecar.verify_spectral_sidecar(
                self.envelope, io.StringIO(self.text, newline="")
            )
        )


if __name__ == "__main__":
    unittest.main()
