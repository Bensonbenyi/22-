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
    return "".join(format(byte, '08b') for byte in data_bytes)


def split_into_payloads(bitstream):
    """切分64位数据块"""
    payloads = []
    total_bits = len(bitstream)

    for i in range(0, total_bits, PAYLOAD_LEN):
        payload = bitstream[i:i + PAYLOAD_LEN]
        # if len(payload) < PAYLOAD_LEN:
        #     payload = payload.ljust(PAYLOAD_LEN, '0')
        #     print(f"最后一块填充: {len(payload)}位")
        # 注意：这里不需要手动补0，build_frame会自动处理
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

    # 3. 切分数据块
    payload_chunks = split_into_payloads(bitstream)

    # 4. 生成带序号的帧
    frames = []
    for i, chunk in enumerate(payload_chunks):
        # 传入 chunk 和 当前帧序号 i
        frame = build_frame(chunk, i)
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

    # 3. 打印第一个帧的结构分析 (用于核对)
    if frames:
        f = frames[0]
        # HEADER(8) | ID(16) | LEN(16) | PAYLOAD(8960) | CRC(16)
        print("\n第一帧结构分析:")
        print(f"Header: {f[:8]}")
        print(f"ID bits: {f[8:24]}")
        print(f"Length bits: {f[24:40]}")  # 16 bits for length
        print(f"Data Sample (first 16 bits): {f[40:56]}")
        print(f"CRC: {f[-16:]}")

    # 保存调试文件
    save_frames(frames, "frames_output.txt")