"""Frozen integer constants for QSOL-MAP fixed FFT profile v0.1.

Runtime analysis performs no trigonometric floating-point evaluation.
"""

FRAME_SIZE = 256
HOP_SIZE = 128
Q15_ONE = 32768
TOP_K = 4

# cos(2*pi*k/256) for k=0..64, frozen to nearest Q15 integer.
TWIDDLE_COS_QUARTER_Q15 = (32768, 32758, 32729, 32679, 32610, 32522, 32413, 32286, 32138, 31972, 31786, 31581, 31357, 31114, 30853, 30572, 30274, 29957, 29622, 29269, 28899, 28511, 28106, 27684, 27246, 26791, 26320, 25833, 25330, 24812, 24279, 23732, 23170, 22595, 22006, 21403, 20788, 20160, 19520, 18868, 18205, 17531, 16846, 16151, 15447, 14733, 14010, 13279, 12540, 11793, 11039, 10279, 9512, 8740, 7962, 7180, 6393, 5602, 4808, 4011, 3212, 2411, 1608, 804, 0)


def _cos_q15(index: int) -> int:
    index %= FRAME_SIZE
    quadrant, offset = divmod(index, 64)
    if quadrant == 0:
        return TWIDDLE_COS_QUARTER_Q15[offset]
    if quadrant == 1:
        return -TWIDDLE_COS_QUARTER_Q15[64 - offset]
    if quadrant == 2:
        return -TWIDDLE_COS_QUARTER_Q15[offset]
    return TWIDDLE_COS_QUARTER_Q15[64 - offset]


TWIDDLE_COS_Q15 = tuple(_cos_q15(index) for index in range(FRAME_SIZE))
TWIDDLE_SIN_Q15 = tuple(
    -TWIDDLE_COS_Q15[(64 - index) % FRAME_SIZE]
    for index in range(FRAME_SIZE)
)

# Exact symmetric triangular window. No float or stored table is required.
WINDOW_WEIGHTS = tuple(
    min(index + 1, FRAME_SIZE - index)
    for index in range(FRAME_SIZE)
)
