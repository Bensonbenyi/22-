"""
video_decode.py - 视频解码与数据恢复
"""

import cv2
import numpy as np
import os
from frame_design import parse_frame, PAYLOAD_LEN

# --- 必须与发送端完全一致的参数 ---
QR_SIZE = 41 
# 考虑到边框(2格)，总格数为 41 + 2*2 = 45
# 假设发送端 scale=15，图像大概 675 像素
# 这里我们用动态计算，不锁死 MODULE_SIZE

def extract_frames(video_path):
    """从视频中提取每一帧"""
    if not os.path.exists(video_path):
        print(f"[-] 错误: 找不到视频文件 {video_path}")
        return []
    
    cap = cv2.VideoCapture(video_path)
    frames = []
    while True:
        ret, frame = cap.read()
        if not ret: break
        frames.append(frame)
    cap.release()
    print(f"[*] 视频读取完成，共提取 {len(frames)} 帧")
    return frames

def get_matrix_from_binary(binary_img):
    """
    核心算法：将二值化图像转回 41x41 矩阵
    目前是“理想状态”解码：假设视频没有形变
    """
    h, w = binary_img.shape
    # 自动计算每个格子的像素大小 (考虑到 2格的 Quiet Zone)
    grid_count = QR_SIZE + 4  # 41 + 2*2
    module_w = w / grid_count
    module_h = h / grid_count

    matrix = np.zeros((QR_SIZE, QR_SIZE), dtype=int)

    for i in range(QR_SIZE):
        for j in range(QR_SIZE):
            # 计算采样点：跳过 2 格边框，取每个格子的中心
            py = int((i + 2.5) * module_h)
            px = int((j + 2.5) * module_w)
            
            # 采样并二值化 (黑色为1, 白色为0)
            if binary_img[py, px] < 128:
                matrix[i, j] = 1
            else:
                matrix[i, j] = 0
    return matrix

def matrix_to_bits(matrix):
    """
    根据 data_mask 提取比特流 (必须跳过定位符)
    """
    # 1. 重新生成 mask (必须与发送端 video_generate.py 完全一致)
    data_mask = np.ones((QR_SIZE, QR_SIZE), dtype=bool)
    data_mask[0:7, 0:7] = False
    data_mask[0:7, QR_SIZE-7:QR_SIZE] = False
    data_mask[QR_SIZE-7:QR_SIZE, 0:7] = False
    # 扣除右下角美化后的 5x5 区域
    data_mask[QR_SIZE-8:QR_SIZE-3, QR_SIZE-8:QR_SIZE-3] = False

    # 2. 提取数据
    available_coords = np.argwhere(data_mask)
    bits = ""
    for r, c in available_coords:
        bits += str(matrix[r, c])
    
    # 只需要返回前 1312 位（Header+ID+Len+Payload+CRC）
    # 这里的 1312 = 8 + 16 + 8 + 1264 + 16
    return bits[:1312]

def process_video_to_bits(video_path):
    """解码全流程"""
    raw_frames = extract_frames(video_path)
    all_frame_bits = []

    for i, frame in enumerate(raw_frames):
        # 1. 预处理
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        _, binary = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY)

        # 2. 采样矩阵
        matrix = get_matrix_from_binary(binary)

        # 3. 转为比特字符串
        bits = matrix_to_bits(matrix)
        all_frame_bits.append(bits)
        
    return all_frame_bits

def save_bits_to_file(frame_bits_list, output_path):
    """
    核心：去重、解析并合成文件
    """
    received_data = {} # 使用字典按 ID 去重 {id: payload}

    for bits in frame_bits_list:
        # 调用之前 frame_design.py 里的解析函数
        # result 应该是 (frame_id, payload_data)
        result = parse_frame(bits)
        
        if result:
            f_id, payload = result
            if f_id not in received_data:
                received_data[f_id] = payload
    
    if not received_data:
        print("[-] 错误：未能解析出任何有效帧")
        return

    # 按 ID 排序并拼接
    sorted_ids = sorted(received_data.keys())
    full_bitstream = "".join(received_data[i] for i in sorted_ids)

    # 比特流转回二进制文件
    byte_list = []
    for i in range(0, len(full_bitstream), 8):
        byte_str = full_bitstream[i:i+8]
        if len(byte_str) == 8:
            byte_list.append(int(byte_str, 2))
    
    with open(output_path, "wb") as f:
        f.write(bytes(byte_list))
    print(f"[+] 文件已恢复: {output_path}, 共 {len(sorted_ids)} 帧")

def main():
    video_input = "transmitter_video.mp4" # 发送端生成的视频
    file_output = "out.bin"               # 恢复出的文件

    # 1. 从视频提取比特流
    print(f"[*] 开始处理视频: {video_input}")
    bits_list = process_video_to_bits(video_input)

    # 2. 解析并保存
    save_bits_to_file(bits_list, file_output)

if __name__ == "__main__":
    main()