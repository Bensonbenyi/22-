"""
video_decode.py - 视频解码与数据恢复
"""

import cv2
import numpy as np
import os
from frame_design import parse_frame, PAYLOAD_LEN
from perspective_transform import correct_frame, reset_frame_hash

QR_SIZE = 41
FRAME_BITS = 1480  # 更新为新的帧长度：8 + 16 + 8 + 1432 + 16 = 1480


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
# 2. 采样（修正：只采样，不画图）
# =========================
def get_matrix_from_binary(qr_img):
    # 先做一次全局二值化，提高 patch 均值判断的准确度
    _, binary = cv2.threshold(qr_img, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    
    # 透视变换后的图片是 674x674，45x45 格子
    # 674 / 45 ≈ 15 像素/格
    unit = 674 / 45  # 每格约 15 像素
    matrix = np.zeros((QR_SIZE, QR_SIZE), dtype=int)

    for i in range(QR_SIZE):
        for j in range(QR_SIZE):
            # 计算采样中心点：跳过 2 格白边，采样点在 (i+0.5) 格
            cy = int((2 + i + 0.5) * unit)
            cx = int((2 + j + 0.5) * unit)
            
            # 5x5 区域采样（比 3x3 更稳，不容易被压缩噪点干扰）
            patch = binary[max(0,cy-2):cy+3, max(0,cx-2):cx+3]
            
            # 核心：均值 < 127 代表黑色，存为 1
            matrix[i, j] = 1 if np.mean(patch) < 127 else 0
            
    return matrix

# =========================
# 3. 提取比特（修正：严格对齐发送端 Mask）
# =========================
def matrix_to_bits(matrix):
    # 建立一个"数据掩码"
    # 默认全部是数据 (True)
    is_data = np.ones((QR_SIZE, QR_SIZE), dtype=bool)

    # 剔除四个角的 7x7 定位符区域 (False)
    is_data[0:7, 0:7] = False
    is_data[0:7, QR_SIZE-7:QR_SIZE] = False
    is_data[QR_SIZE-7:QR_SIZE, 0:7] = False
    is_data[QR_SIZE-7:QR_SIZE, QR_SIZE-7:QR_SIZE] = False

    bits = []
    # 按照行优先顺序提取所有 True (数据) 区域
    for i in range(QR_SIZE):
        for j in range(QR_SIZE):
            if is_data[i, j]:
                bits.append(str(matrix[i, j]))
    
    # 拼接成字符串并截断到 header+payload 的固定长度
    return "".join(bits)[:FRAME_BITS]

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

        qr = get_corrected_qr(frame)
        if qr is None:
            continue
        
        if isinstance(qr, str) and qr == "SKIP":
            continue

        matrix = get_matrix_from_binary(qr)
        bits = matrix_to_bits(matrix)

        all_bits.append(bits)
        success += 1

    cap.release()

    print(f"[*] 总帧: {frame_count} | 成功提取: {success}")
    return all_bits


# =========================
# 5. 保存文件
# =========================
def save_bits_to_file(frame_bits_list, output_path):
    received = {}
    HEADER = "10101010"

    ok = 0
    fail = 0

    for bits in frame_bits_list:
        # Header 对齐
        if not bits.startswith(HEADER):
            idx = bits.find(HEADER)
            if 0 <= idx < 20:
                bits = bits[idx:].ljust(FRAME_BITS, '0')

        f_id, payload = parse_frame(bits)

        if payload is not None:
            ok += 1
            if f_id not in received:
                received[f_id] = payload
        else:
            fail += 1

    print(f"[解析统计] 成功:{ok} 失败:{fail}")

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
# 6. 文件对比（不动）
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

    bits = process_video_to_bits(video_input)
    save_bits_to_file(bits, file_output)
    compare_files(file_output, original_file)


if __name__ == "__main__":
    main()