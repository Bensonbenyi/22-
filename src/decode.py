import os
import cv2
import numpy as np

# ==========================
# 成员3：数据解码
# 功能：把帧恢复成二进制文件
# ==========================

def parse_frames(frame_dir="dframes"):
    """
    1. 解析所有帧 -> 提取 0 和 1
    黑=0，白=1
    """
    bits = []
    frame_files = sorted(os.listdir(frame_dir))

    for file in frame_files:
        path = os.path.join(frame_dir, file)
        img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
        avg = np.mean(img)
        bit = 1 if avg > 128 else 0
        bits.append(bit)

    return bits


def merge_bits(bits):
    """
    2. 把 0/1 合并成字节（8位一组）
    """
    bytes_data = []
    for i in range(0, len(bits), 8):
        byte = 0
        for j in range(8):
            if i + j < len(bits):
                byte = (byte << 1) | bits[i + j]
        bytes_data.append(byte)

    return bytes_data


def write_file(bytes_data, output_path="vout.bin"):
    """
    3. 写入文件，输出最终恢复的数据
    """
    with open(output_path, "wb") as f:
        f.write(bytes(bytes_data))


# ==========================
# 主流程（你任务的完整流程）
# ==========================
if __name__ == "__main__":
    print("正在解码...")

    # 1. 解析帧
    bits = parse_frames()

    # 2. 合并bit
    data = merge_bits(bits)

    # 3. 写入文件
    write_file(data)

    print("解码完成！输出：vout.bin")