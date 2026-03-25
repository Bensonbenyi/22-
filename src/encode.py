"""
encode.py - 数据编码模块

将二进制文件编码为帧列表
"""

import os
# 导入操作系统模块，用于文件路径判断和获取文件大小
from frame_design import build_frame, PAYLOAD_LEN
# 从帧设计模块导入构建帧的函数和有效载荷长度常量


def read_file(file_path):
    """读取二进制文件"""
    try:
        with open(file_path, 'rb') as f:  # 以二进制只读模式打开文件
            data = f.read()  # 读取文件全部内容
        print(f"读取文件: {file_path}, 大小: {len(data)} 字节")  # 打印读取信息
        return data  # 返回字节数据
    except FileNotFoundError:
        print(f"错误: 找不到文件 {file_path}")  # 文件不存在时打印错误
        return None  # 返回None表示读取失败


def bytes_to_bits(data_bytes):
    """字节转比特串"""
    # 将每个字节转换为8位二进制字符串，然后拼接成一个长字符串
    return "".join(format(byte, '08b') for byte in data_bytes)


def split_into_payloads(bitstream):
    """切分64位数据块"""
    payloads = []  # 存储切分后的数据块
    total_bits = len(bitstream)  # 获取比特串总长度

    # 按PAYLOAD_LEN步长遍历，切分数据块
    for i in range(0, total_bits, PAYLOAD_LEN):
        payload = bitstream[i:i + PAYLOAD_LEN]  # 取出当前块
        # 注意：这里不需要手动补0，build_frame会自动处理
        payloads.append(payload)  # 添加到列表

    return payloads  # 返回切分后的数据块列表


def generate_frames(file_path):
    """从文件生成帧列表"""
    # 1. 读取文件
    data_bytes = read_file(file_path)  # 调用读取函数获取字节数据
    if data_bytes is None:  # 如果读取失败
        return []  # 返回空列表

    # 2. 转比特串
    bitstream = bytes_to_bits(data_bytes)  # 将字节转换为比特串
    print(f"比特串长度: {len(bitstream)} 位")  # 打印比特串长度

    # 3. 切分数据块
    payload_chunks = split_into_payloads(bitstream)  # 按有效载荷长度切分

    # 4. 生成带序号的帧
    frames = []  # 存储所有帧
    for i, chunk in enumerate(payload_chunks):  # 遍历每个数据块，i是帧序号
        # 传入数据块和当前帧序号，构建完整帧
        frame = build_frame(chunk, i)
        frames.append(frame)  # 添加到帧列表

    print(f"生成帧数: {len(frames)}")  # 打印生成的帧数量
    return frames  # 返回帧列表


def save_frames(frames, output_file):
    """保存帧到文件（调试用）"""
    with open(output_file, 'w') as f:  # 以文本写入模式打开文件
        for i, frame in enumerate(frames):  # 遍历所有帧
            f.write(f"帧{i}: {frame}\n")  # 写入帧序号和帧内容
    print(f"帧已保存到: {output_file}")  # 打印保存成功信息


def get_file_info(file_path):
    """获取文件信息"""
    if not os.path.exists(file_path):  # 判断文件是否存在
        return 0  # 不存在则返回0

    file_size = os.path.getsize(file_path)  # 获取文件大小（字节）
    total_bits = file_size * 8  # 计算总比特数
    # 计算需要多少帧（向上取整）
    frame_count = (total_bits + PAYLOAD_LEN - 1) // PAYLOAD_LEN

    print("=" * 40)  # 打印分隔线
    print("文件信息:")
    print(f"大小: {file_size} 字节")  # 打印文件大小
    print(f"总比特: {total_bits} 位")  # 打印总比特数
    print(f"需要帧数: {frame_count}")  # 打印需要的帧数
    print("=" * 40)  # 打印分隔线

    return frame_count  # 返回帧数


def encode_file(input_file):
    """编码主函数"""
    print(f"\n开始编码: {input_file}")  # 打印开始编码信息

    # 显示文件信息
    get_file_info(input_file)  # 调用函数显示文件信息

    # 生成帧
    frames = generate_frames(input_file)  # 调用生成帧函数

    return frames  # 返回帧列表


if __name__ == "__main__":
    # 测试代码
    test_file = "input.bin"  # 定义测试文件名

    # 创建测试文件
    if not os.path.exists(test_file):  # 如果测试文件不存在
        with open(test_file, 'wb') as f:  # 以二进制写入模式打开
            f.write(b"Hello World! Test data for encoding.")  # 写入测试数据
        print(f"创建测试文件: {test_file}")  # 打印创建成功信息

    # 编码测试
    frames = encode_file(test_file)  # 调用编码函数

    # 3. 打印第一个帧的结构分析 (用于核对)
    if frames:  # 如果帧列表不为空
        f = frames[0]  # 获取第一帧
        # HEADER(8) | ID(16) | LEN(16) | PAYLOAD(8960) | CRC(16)
        print("\n第一帧结构分析:")
        print(f"Header: {f[:8]}")  # 打印前8位（帧头）
        print(f"ID bits: {f[8:24]}")  # 打印8-24位（帧ID）
        print(f"Length bits: {f[24:40]}")  # 打印24-40位（长度字段）
        print(f"Data Sample (first 16 bits): {f[40:56]}")  # 打印40-56位（数据前16位）
        print(f"CRC: {f[-16:]}")  # 打印最后16位（CRC校验）

    # 保存调试文件
    save_frames(frames, "frames_output.txt")  # 将帧保存到文件