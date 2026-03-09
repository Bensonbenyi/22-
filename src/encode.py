"""
encode.py - 数据编码模块

将二进制文件编码为帧列表
"""

import os
from frame_design import build_frame, PAYLOAD_LEN


def read_file(file_path):
    """读取二进制文件"""
    try:
        with open(file_path, 'rb') as f:
            data = f.read()
        print(f"读取文件: {file_path}, 大小: {len(data)} 字节")
        return data
    except FileNotFoundError:
        print(f"错误: 找不到文件 {file_path}")
        return None


def bytes_to_bits(data_bytes):
    """字节转比特串"""
    bits = ''
    for byte in data_bytes:
        bits += format(byte, '08b')
    return bits


def split_into_payloads(bitstream):
    """切分64位数据块"""
    payloads = []
    total_bits = len(bitstream)

    for i in range(0, total_bits, PAYLOAD_LEN):
        payload = bitstream[i:i + PAYLOAD_LEN]
        if len(payload) < PAYLOAD_LEN:
            payload = payload.ljust(PAYLOAD_LEN, '0')
            print(f"最后一块填充: {len(payload)}位")
        payloads.append(payload)

    return payloads


def generate_frames(file_path):
    """从文件生成帧列表"""
    # 1. 读取文件
    data_bytes = read_file(file_path)
    if data_bytes is None:
        return []

    # 2. 转比特串
    bitstream = bytes_to_bits(data_bytes)
    print(f"比特串长度: {len(bitstream)} 位")

    # 3. 切分payload
    payloads = split_into_payloads(bitstream)

    # 4. 生成帧
    frames = []
    for payload in payloads:
        frame = build_frame(payload)
        frames.append(frame)

    print(f"生成帧数: {len(frames)}")
    return frames


def save_frames(frames, output_file):
    """保存帧到文件（调试用）"""
    with open(output_file, 'w') as f:
        for i, frame in enumerate(frames):
            f.write(f"帧{i}: {frame}\n")
    print(f"帧已保存到: {output_file}")


def get_file_info(file_path):
    """获取文件信息"""
    if not os.path.exists(file_path):
        return 0

    file_size = os.path.getsize(file_path)
    total_bits = file_size * 8
    frame_count = (total_bits + PAYLOAD_LEN - 1) // PAYLOAD_LEN

    print("=" * 40)
    print("文件信息:")
    print(f"大小: {file_size} 字节")
    print(f"总比特: {total_bits} 位")
    print(f"需要帧数: {frame_count}")
    print("=" * 40)

    return frame_count


def encode_file(input_file):
    """编码主函数"""
    print(f"\n开始编码: {input_file}")

    # 显示文件信息
    get_file_info(input_file)

    # 生成帧
    frames = generate_frames(input_file)

    return frames


if __name__ == "__main__":
    # 测试代码
    test_file = "input.bin"

    # 创建测试文件
    if not os.path.exists(test_file):
        with open(test_file, 'wb') as f:
            f.write(b"Hello World! Test data for encoding.")
        print(f"创建测试文件: {test_file}")

    # 编码测试
    frames = encode_file(test_file)

    # 显示前3个帧
    print("\n前3个帧:")
    for i in range(min(3, len(frames))):
        frame = frames[i]
        print(f"帧{i}: {frame}")
        print(f"    头:{frame[:8]} 数据:{frame[8:72]} CRC:{frame[72:]}")

    # 保存调试文件
    save_frames(frames, "frames_output.txt")