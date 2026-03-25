"""
video_decode.py - 视频解码与数据恢复 (1920x1080 适配版，128x72矩阵，11x11定位点，无白边)
"""

import cv2
import numpy as np
import os
from frame_design import parse_frame, PAYLOAD_LEN, QR_WIDTH, QR_HEIGHT, FINDER_SIZE, FRAME_LEN
from perspective_transform import correct_frame, reset_frame_hash

# 视频和矩阵配置
VIDEO_WIDTH = 1920
VIDEO_HEIGHT = 1080
CELL_SIZE = 15  # 每个矩阵格子的像素大小
BORDER_CELLS = 0  # 无白边

# 透视变换输出大小（无白边，直接就是 1920x1080）
OUTPUT_WIDTH = VIDEO_WIDTH   # 1920
OUTPUT_HEIGHT = VIDEO_HEIGHT  # 1080

FRAME_BITS = FRAME_LEN  # 从 frame_design 导入


def get_matrix_from_frame_direct(frame):
    """
    直接从原始帧采样矩阵（不进行透视变换）
    适用于视频帧已经是正视图的情况
    【无白边版本】
    """
    # 转换为灰度图
    if len(frame.shape) == 3:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    else:
        gray = frame

    # 二值化
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # 计算每格像素大小
    unit_x = gray.shape[1] / QR_WIDTH   # 1920 / 128 = 15
    unit_y = gray.shape[0] / QR_HEIGHT  # 1080 / 72 = 15

    matrix = np.zeros((QR_HEIGHT, QR_WIDTH), dtype=int)

    for i in range(QR_HEIGHT):
        for j in range(QR_WIDTH):
            # 【无白边】直接从 (0, 0) 开始采样
            cy = int((i + 0.5) * unit_y)
            cx = int((j + 0.5) * unit_x)

            # 5x5 区域采样
            patch = binary[max(0,cy-2):cy+3, max(0,cx-2):cx+3]

            # 均值 < 127 代表黑色，存为 1
            matrix[i, j] = 1 if np.mean(patch) < 127 else 0

    return matrix


# =========================
# 1. 定位并截取（使用透视变换）
# =========================
def get_corrected_qr(frame):
    # 使用 perspective_transform.py 中的 correct_frame 进行透视变换
    result = correct_frame(frame)

    if result is None:
        return None

    if isinstance(result, str) and result == "SKIP":
        return "SKIP"

    # 转换为灰度图
    gray = cv2.cvtColor(result, cv2.COLOR_BGR2GRAY)

    return gray


# =========================
# 2. 采样（适配 128x72 矩阵，无白边）
# =========================
def get_matrix_from_binary(qr_img):
    """
    从透视变换后的图像采样 128x72 矩阵
    图像大小应该是 1920x1080（无白边）
    """
    # 先做一次全局二值化
    _, binary = cv2.threshold(qr_img, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    h, w = binary.shape

    # 计算每格的像素大小
    # 总宽度 = 1920，格子数 = 128
    unit_x = w / QR_WIDTH   # 1920 / 128 = 15
    unit_y = h / QR_HEIGHT  # 1080 / 72 = 15

    matrix = np.zeros((QR_HEIGHT, QR_WIDTH), dtype=int)

    for i in range(QR_HEIGHT):
        for j in range(QR_WIDTH):
            # 【无白边】直接计算采样点
            cy = int((i + 0.5) * unit_y)
            cx = int((j + 0.5) * unit_x)

            # 确保不越界
            if cy < 0 or cy >= h or cx < 0 or cx >= w:
                matrix[i, j] = 0
                continue

            # 5x5 区域采样
            patch = binary[max(0,cy-2):min(h,cy+3), max(0,cx-2):min(w,cx+3)]

            # 均值 < 127 代表黑色，存为 1
            if patch.size > 0:
                matrix[i, j] = 1 if np.mean(patch) < 127 else 0
            else:
                matrix[i, j] = 0

    return matrix


# =========================
# 3. 提取比特（适配 128x72 矩阵）
# =========================
def matrix_to_bits(matrix):
    """
    从 128x72 矩阵提取数据比特
    扣除四个角的 11x11 定位符区域
    """
    # 建立数据掩码
    is_data = np.ones((QR_HEIGHT, QR_WIDTH), dtype=bool)

    # 剔除四个角的 11x11 定位符区域
    is_data[0:FINDER_SIZE, 0:FINDER_SIZE] = False
    is_data[0:FINDER_SIZE, QR_WIDTH-FINDER_SIZE:QR_WIDTH] = False
    is_data[QR_HEIGHT-FINDER_SIZE:QR_HEIGHT, 0:FINDER_SIZE] = False
    is_data[QR_HEIGHT-FINDER_SIZE:QR_HEIGHT, QR_WIDTH-FINDER_SIZE:QR_WIDTH] = False

    bits = []
    # 按照行优先顺序提取所有 True (数据) 区域
    for i in range(QR_HEIGHT):
        for j in range(QR_WIDTH):
            if is_data[i, j]:
                bits.append(str(matrix[i, j]))

    # 拼接成字符串并截断到帧长度
    return "".join(bits)[:FRAME_BITS]


def try_decode_frame(frame):
    """
    尝试解码单帧，先尝试透视变换，如果失败则直接采样
    """
    HEADER = "10101010"

    # 方法1：使用透视变换
    qr = get_corrected_qr(frame)
    if qr is not None and not isinstance(qr, str):
        matrix = get_matrix_from_binary(qr)
        bits = matrix_to_bits(matrix)
        if bits.startswith(HEADER):
            return bits

    # 方法2：直接采样（适用于正视图视频）
    matrix = get_matrix_from_frame_direct(frame)
    bits = matrix_to_bits(matrix)
    if bits.startswith(HEADER):
        return bits

    # 尝试对齐 Header
    idx = bits.find(HEADER)
    if 0 <= idx < 20:
        bits = bits[idx:].ljust(FRAME_BITS, '0')
        return bits

    return bits  # 返回原始比特，可能后续能解析


# =========================
# 4. 视频处理
# =========================
def process_video_to_bits(video_path):
    cap = cv2.VideoCapture(video_path)

    all_bits = []
    frame_count = 0
    success = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        frame_count += 1

        bits = try_decode_frame(frame)

        if bits:
            all_bits.append(bits)
            success += 1

    cap.release()

    print(f"[*] 总帧: {frame_count} | 成功提取: {success}")
    return all_bits


# =========================
# 5. 保存文件
# =========================
def save_bits_to_file(frame_bits_list, output_path, max_frame_id=None):
    received = {}
    HEADER = "10101010"

    ok = 0
    fail = 0
    skipped = 0

    for bits in frame_bits_list:
        # Header 对齐
        if not bits.startswith(HEADER):
            idx = bits.find(HEADER)
            if 0 <= idx < 20:
                bits = bits[idx:].ljust(FRAME_BITS, '0')

        f_id, payload = parse_frame(bits)

        if payload is not None:
            # 检查帧ID是否在合理范围内
            if max_frame_id is not None and f_id > max_frame_id:
                skipped += 1
                continue
            ok += 1
            if f_id not in received:
                received[f_id] = payload
        else:
            fail += 1

    print(f"[解析统计] 成功:{ok} 失败:{fail} 跳过(超出范围):{skipped}")

    if not received:
        print("[-] 没有有效帧")
        return

    sorted_ids = sorted(received.keys())
    bitstream = "".join(received[i] for i in sorted_ids)

    data = [
        int(bitstream[i:i+8], 2)
        for i in range(0, len(bitstream), 8)
        if i + 8 <= len(bitstream)
    ]

    with open(output_path, "wb") as f:
        f.write(bytes(data))

    print(f"[+] 恢复完成！帧数: {len(sorted_ids)}")


# =========================
# 6. 文件对比
# =========================
def compare_files(decoded_file, original_file, output_file="vout.bin"):
    if not os.path.exists(decoded_file) or not os.path.exists(original_file):
        print("[-] 缺少文件")
        return False

    with open(decoded_file, "rb") as f:
        dec = f.read()
    with open(original_file, "rb") as f:
        ori = f.read()

    max_len = max(len(dec), len(ori))
    res = []

    for i in range(max_len):
        if i < len(dec) and i < len(ori):
            res.append((~(dec[i] ^ ori[i])) & 0xFF)
        else:
            res.append(0)

    with open(output_file, "wb") as f:
        f.write(bytes(res))

    correct = sum(bin(b).count("1") for b in res)
    total = max_len * 8

    print(f"[+] 准确率: {correct / total * 100:.2f}%")
    return True


# =========================
# main
# =========================
def main():
    video_input = "transmitter_video.mp4"
    file_output = "out.bin"
    original_file = "input.bin"

    # 重置帧哈希缓存，确保每次运行都是全新的处理
    reset_frame_hash()

    # 计算预期的最大帧数（基于原始文件大小）
    import os
    if os.path.exists(original_file):
        original_size = os.path.getsize(original_file)
        # 每帧payload字节数 = PAYLOAD_LEN // 8
        payload_bytes = PAYLOAD_LEN // 8
        expected_frames = (original_size + payload_bytes - 1) // payload_bytes  # 向上取整
        max_frame_id = expected_frames + 2  # 允许一些冗余
        print(f"[信息] 原始文件: {original_size} bytes, 预期帧数: {expected_frames}, 最大帧ID: {max_frame_id}")
    else:
        max_frame_id = None

    bits = process_video_to_bits(video_input)
    save_bits_to_file(bits, file_output, max_frame_id)
    compare_files(file_output, original_file)


if __name__ == "__main__":
    main()
