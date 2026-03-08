"""
Frame Design Module

Frame structure (88 bits total):

| HEADER (8) | PAYLOAD (64) | CRC (16) |

HEADER : fixed pattern for synchronization
PAYLOAD: actual data bits
CRC    : error detection
"""

HEADER = "10101010"

HEADER_LEN = 8
PAYLOAD_LEN = 64
CRC_LEN = 16
FRAME_LEN = HEADER_LEN + PAYLOAD_LEN + CRC_LEN


# -----------------------------
# CRC计算
# -----------------------------
def compute_crc(payload_bits: str) -> str:
    """
    Simple CRC implementation
    Here we use a very simple checksum-style CRC
    """

    value = int(payload_bits, 2)

    crc = value % (2 ** CRC_LEN)

    return format(crc, f'0{CRC_LEN}b')


# -----------------------------
# 构建帧
# -----------------------------
def build_frame(payload_bits: str) -> str:
    """
    Build a frame from payload

    input:
        payload_bits (64 bit string)

    output:
        frame_bits (88 bit string)
    """

    if len(payload_bits) != PAYLOAD_LEN:
        raise ValueError("Payload must be 64 bits")

    crc = compute_crc(payload_bits)

    frame = HEADER + payload_bits + crc

    return frame


# -----------------------------
# 解析帧
# -----------------------------
def parse_frame(frame_bits: str):
    """
    Parse frame and check CRC

    return:
        payload_bits or None if invalid
    """

    if len(frame_bits) != FRAME_LEN:
        return None

    header = frame_bits[:HEADER_LEN]
    payload = frame_bits[HEADER_LEN:HEADER_LEN + PAYLOAD_LEN]
    crc = frame_bits[HEADER_LEN + PAYLOAD_LEN:]

    if header != HEADER:
        return None

    if compute_crc(payload) != crc:
        return None

    return payload


# -----------------------------
# bitstream → frames
# -----------------------------
def split_bitstream(bitstream: str):
    """
    Split long bitstream into frames
    """

    frames = []

    for i in range(0, len(bitstream), PAYLOAD_LEN):

        payload = bitstream[i:i + PAYLOAD_LEN]

        if len(payload) < PAYLOAD_LEN:
            payload = payload.ljust(PAYLOAD_LEN, "0")

        frame = build_frame(payload)

        frames.append(frame)

    return frames


# -----------------------------
# frames → bitstream
# -----------------------------
def frames_to_bitstream(frames):
    """
    Extract payloads from frames
    """

    bitstream = ""

    for frame in frames:

        payload = parse_frame(frame)

        if payload is not None:
            bitstream += payload

    return bitstream