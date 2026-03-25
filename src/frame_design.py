"""
Smart-Grid Frame Design Module (Optimized for 1920x1080, No Border)

Frame Structure (Total bits: 8728 bits ≈ 1091 Bytes):
| HEADER(8) | FRAME_ID(16) | DATA_LEN(16) | PAYLOAD(8672) | CRC(16) |

HEADER   : Synchronization pattern "10101010"
FRAME_ID : 0-65535, tracks frame order
DATA_LEN : 0-1084, how many BYTES in this payload are real data
PAYLOAD  : Actual data bits (8672 bits max = 1084 bytes)
CRC      : Error detection

Video Size: 1920 x 1080 (无白边)
Cell Size: 15 pixels
Matrix Size: 128 x 72 (1920/15 x 1080/15)
Finder Size: 11x11 (更大的定位点，便于检测)
Total cells: 9216
- 4 corner finders (11x11): 4 * 121 = 484 cells
- Data area: 9216 - 484 = 8732 bits
"""

HEADER = "10101010"
HEADER_LEN = 8
ID_LEN = 16
LEN_FIELD_BIT = 16      # 16位长度字段
PAYLOAD_LEN = 8672      # 1084 字节 * 8 = 8672 bits (调整后，无白边)
CRC_LEN = 16

# 总帧长：8 + 16 + 16 + 8672 + 16 = 8728 bits
FRAME_LEN = HEADER_LEN + ID_LEN + LEN_FIELD_BIT + PAYLOAD_LEN + CRC_LEN
MAX_FRAME_ID = (1 << ID_LEN) - 1
MAX_PAYLOAD_BYTES = PAYLOAD_LEN // 8

# 视频和二维码配置
VIDEO_WIDTH = 1920      # 视频宽度
VIDEO_HEIGHT = 1080     # 视频高度
CELL_SIZE = 15          # 每个格子15像素
BORDER_CELLS = 0        # 无白边
FINDER_SIZE = 11        # 定位点11x11（更大，便于检测）

# 二维码矩阵大小（无白边，直接占满整个画面）
QR_WIDTH = VIDEO_WIDTH // CELL_SIZE   # 1920/15 = 128
QR_HEIGHT = VIDEO_HEIGHT // CELL_SIZE  # 1080/15 = 72


def _is_binary_string(value: str) -> bool:
    """检查输入是否仅由 0/1 组成。"""
    return set(value) <= {"0", "1"}

def compute_crc(data_string: str) -> str:
    """计算从 FRAME_ID 到 PAYLOAD 的校验和"""
    value = int(data_string, 2)
    crc = value % (2 ** CRC_LEN)
    return format(crc, f'0{CRC_LEN}b')

def build_frame(payload_bits: str, frame_id: int) -> str:
    """
    构建帧：解决填充0导致无法区分的问题
    """
    if not _is_binary_string(payload_bits):
        raise ValueError("payload_bits 必须只包含 0 和 1")
    if len(payload_bits) > PAYLOAD_LEN:
        raise ValueError(f"payload_bits 不能超过 {PAYLOAD_LEN} bits")
    if not 0 <= frame_id <= MAX_FRAME_ID:
        raise ValueError(f"frame_id 必须在 0 到 {MAX_FRAME_ID} 之间")

    # 计算当前这帧实际包含的字节数
    actual_bytes_count = len(payload_bits) // 8
    if actual_bytes_count > MAX_PAYLOAD_BYTES:
        raise ValueError(f"payload_bits 不能超过 {MAX_PAYLOAD_BYTES} 字节")

    # 如果不足 PAYLOAD_LEN，进行补齐
    if len(payload_bits) < PAYLOAD_LEN:
        payload_bits = payload_bits.ljust(PAYLOAD_LEN, "0")

    # 转换元数据为二进制
    id_bits = format(frame_id, f'0{ID_LEN}b')
    len_bits = format(actual_bytes_count, f'0{LEN_FIELD_BIT}b')

    # 计算校验范围：ID + LEN + PAYLOAD
    check_area = id_bits + len_bits + payload_bits
    crc = compute_crc(check_area)

    return HEADER + check_area + crc

def parse_frame(frame_bits: str):
    """
    解析帧并利用 DATA_LEN 裁剪掉末尾填充的0
    """
    if len(frame_bits) != FRAME_LEN:
        return None, None
    if not _is_binary_string(frame_bits):
        return None, None

    header = frame_bits[:HEADER_LEN]
    if header != HEADER:
        return None, None

    # 拆分内容
    id_start = HEADER_LEN
    len_start = id_start + ID_LEN
    payload_start = len_start + LEN_FIELD_BIT
    crc_start = payload_start + PAYLOAD_LEN

    frame_id = int(frame_bits[id_start:len_start], 2)
    data_len_in_bytes = int(frame_bits[len_start:payload_start], 2)
    payload = frame_bits[payload_start:crc_start]
    received_crc = frame_bits[crc_start:]

    # 校验
    check_area = frame_bits[id_start:crc_start]
    if compute_crc(check_area) != received_crc:
        return None, None

    # 根据 data_len_in_bytes 只截取有效数据
    if data_len_in_bytes > MAX_PAYLOAD_BYTES:
        return None, None
    valid_bit_count = data_len_in_bytes * 8
    real_payload = payload[:valid_bit_count]

    return frame_id, real_payload

def split_bitstream(bitstream: str):
    """
    将长比特流分割成帧
    """
    if not _is_binary_string(bitstream):
        raise ValueError("bitstream 必须只包含 0 和 1")

    frames = []
    frame_counter = 0

    for i in range(0, len(bitstream), PAYLOAD_LEN):
        chunk = bitstream[i:i + PAYLOAD_LEN]
        frame = build_frame(chunk, frame_counter)
        frames.append(frame)
        frame_counter += 1

    return frames

def frames_to_bitstream(frames):
    """
    从所有帧中提取并排序拼接有效数据
    """
    payload_dict = {}

    for frame in frames:
        f_id, payload = parse_frame(frame)
        if f_id is not None:
            payload_dict[f_id] = payload

    # 根据 Frame ID 排序，确保文件内容顺序正确
    sorted_ids = sorted(payload_dict.keys())
    full_bitstream = "".join(payload_dict[i] for i in sorted_ids)

    return full_bitstream
