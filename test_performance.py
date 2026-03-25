"""
视频传输性能测试脚本
测量指标：
1. 有效传输量（bits）：从第一个位开始，直到遇到第一个未被标记但实际错误的位
2. 总传输量（bits）：规定时长内传输的总比特数（不含前导同步码）
3. 有效传输率（bps）：有效传输量 / 视频播放时长
4. 误码率（BER, %）：未标记错误但接收错误的比特数 ÷ 总传输量
5. 丢失率（%）：被标记为错误（不可用）的比特数 ÷ 总传输量

使用方法:
    python test_performance.py <original.bin> <decoded.bin> <video.mp4> [duration_ms]
    
示例:
    python test_performance.py input.bin out.bin transmitter_video.mp4 1000
"""

import sys
import os
import cv2

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from frame_design import (
    HEADER, HEADER_LEN, ID_LEN, LEN_FIELD_BIT, 
    PAYLOAD_LEN, CRC_LEN, FRAME_LEN, parse_frame
)


def bits_to_bytes(bits_str):
    """将比特字符串转换为字节列表"""
    bytes_list = []
    for i in range(0, len(bits_str), 8):
        byte_str = bits_str[i:i+8]
        if len(byte_str) == 8:
            bytes_list.append(int(byte_str, 2))
    return bytes(bytes_list)


def bytes_to_bits(data_bytes):
    """将字节转换为比特字符串"""
    return ''.join(format(b, '08b') for b in data_bytes)


def get_video_duration(video_path):
    """获取视频时长（秒）"""
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
    cap.release()
    
    if fps > 0:
        return frame_count / fps
    return 0


def extract_all_frames_bits(video_path, use_dedup=True):
    """
    从视频中提取所有帧的比特流（包括成功和失败的）
    返回: list of (frame_bits, is_valid, frame_id, payload)
    
    参数:
        use_dedup: 是否使用透视变换的去重逻辑（和 decode 保持一致）
    """
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))
    from video_decode import get_matrix_from_binary, matrix_to_bits, get_matrix_from_frame_direct
    from perspective_transform import correct_frame, reset_frame_hash
    import cv2
    import numpy as np
    
    # 重置帧哈希
    reset_frame_hash()
    
    cap = cv2.VideoCapture(video_path)
    all_frames = []
    skipped_count = 0
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        
        # 使用透视变换
        result = correct_frame(frame)
        
        if isinstance(result, str) and result == "SKIP":
            # 被去重逻辑跳过（重复帧）
            skipped_count += 1
            if use_dedup:
                # 如果使用去重，跳过这一帧
                continue
            else:
                # 如果不使用去重，用直接采样处理
                matrix = get_matrix_from_frame_direct(frame)
                bits = matrix_to_bits(matrix)
        elif result is not None:
            # 透视变换成功
            gray = cv2.cvtColor(result, cv2.COLOR_BGR2GRAY)
            matrix = get_matrix_from_binary(gray)
            bits = matrix_to_bits(matrix)
        else:
            # 透视变换失败，尝试直接采样
            matrix = get_matrix_from_frame_direct(frame)
            bits = matrix_to_bits(matrix)
        
        if bits:
            # 尝试对齐 Header
            if not bits.startswith(HEADER):
                idx = bits.find(HEADER)
                if 0 <= idx < 20:
                    bits = bits[idx:].ljust(FRAME_LEN, '0')
            
            # 尝试解析帧
            f_id, payload = parse_frame(bits)
            if f_id is not None and payload is not None:
                all_frames.append({
                    'bits': bits,
                    'is_valid': True,
                    'frame_id': f_id,
                    'payload': payload,
                    'error_type': None
                })
            else:
                # CRC 校验失败或其他错误
                all_frames.append({
                    'bits': bits,
                    'is_valid': False,
                    'frame_id': None,
                    'payload': None,
                    'error_type': 'CRC_FAIL'
                })
        else:
            # 完全无法解码
            all_frames.append({
                'bits': None,
                'is_valid': False,
                'frame_id': None,
                'payload': None,
                'error_type': 'DECODE_FAIL'
            })
    
    cap.release()
    return all_frames, skipped_count


def calculate_performance_metrics(original_file, decoded_file, video_path, duration_ms=None):
    """
    计算传输性能指标
    """
    print("="*60)
    print("视频传输性能测试")
    print("="*60)
    
    # 1. 读取原始数据
    with open(original_file, 'rb') as f:
        original_data = f.read()
    original_bits = bytes_to_bits(original_data)
    
    # 2. 读取解码数据
    with open(decoded_file, 'rb') as f:
        decoded_data = f.read()
    decoded_bits = bytes_to_bits(decoded_data)
    
    # 3. 获取视频信息
    video_duration = get_video_duration(video_path)
    print(f"\n[视频信息]")
    print(f"  视频时长: {video_duration*1000:.2f} ms")
    print(f"  指定测试时长: {duration_ms} ms" if duration_ms else "  测试时长: 全部")
    
    # 4. 提取视频中的所有帧（使用去重逻辑，和 decode 保持一致）
    print(f"\n[*] 正在分析视频帧...")
    all_frames, skipped_count = extract_all_frames_bits(video_path, use_dedup=True)
    
    # 5. 根据 duration_ms 截取帧（按数据帧而不是视频帧）
    # 注意：这里不需要再按视频帧截取，因为 extract_all_frames_bits 已经处理了去重
    actual_duration_sec = duration_ms / 1000.0 if duration_ms else video_duration
    
    # 6. 统计帧信息
    valid_frames = [f for f in all_frames if f['is_valid']]
    invalid_frames = [f for f in all_frames if not f['is_valid']]
    crc_fail_frames = [f for f in invalid_frames if f.get('error_type') == 'CRC_FAIL']
    decode_fail_frames = [f for f in invalid_frames if f.get('error_type') == 'DECODE_FAIL']
    
    print(f"\n[帧统计]")
    print(f"  提取帧数: {len(all_frames)}")
    print(f"  去重跳过: {skipped_count}")
    print(f"  有效帧: {len(valid_frames)}")
    print(f"  无效帧: {len(invalid_frames)} (CRC失败: {len(crc_fail_frames)}, 解码失败: {len(decode_fail_frames)})")
    
    # 7. 去重并按帧ID排序
    unique_frames = {}
    for f in valid_frames:
        fid = f['frame_id']
        if fid not in unique_frames:
            unique_frames[fid] = f
    
    sorted_frame_ids = sorted(unique_frames.keys())
    
    # 根据 duration_ms 限制帧数
    if duration_ms:
        fps = 15
        frame_repeat = 1
        # 计算在指定时长内应该有多少个数据帧
        max_data_frames = int(duration_ms / 1000.0 * fps / frame_repeat)
        # 只保留前 max_data_frames 个帧ID
        sorted_frame_ids = sorted_frame_ids[:max_data_frames]
        unique_frames = {fid: unique_frames[fid] for fid in sorted_frame_ids}
    
    print(f"  去重后有效帧: {len(unique_frames)} (帧ID: {sorted_frame_ids[:15]}{'...' if len(sorted_frame_ids) > 15 else ''})")
    
    # 8. 计算各项指标
    
    # 总传输量 = 所有尝试传输的比特（不含HEADER）
    # 每帧传输量 = ID_LEN + LEN_FIELD_BIT + PAYLOAD_LEN + CRC_LEN
    bits_per_frame = ID_LEN + LEN_FIELD_BIT + PAYLOAD_LEN + CRC_LEN  # 16+16+8672+16 = 8720
    total_transmitted_bits = len(all_frames) * bits_per_frame
    
    # 标记为错误的比特（丢失）= 无效帧对应的比特数
    marked_error_bits = len(invalid_frames) * bits_per_frame
    
    # 有效帧中的实际错误比特数（与原始数据对比）
    actual_error_bits = 0
    checked_bits = 0
    
    # 构建原始数据的帧映射（假设每帧PAYLOAD_LEN比特）
    original_payload_len = PAYLOAD_LEN
    
    # 计算有效传输量：从第一个位开始，直到遇到第一个实际错误的位
    effective_bits = 0
    first_error_found = False
    
    print(f"\n[*] 正在逐帧对比...")
    
    for fid in sorted_frame_ids:
        if first_error_found:
            break
            
        frame = unique_frames[fid]
        payload = frame['payload']
        payload_bit_len = len(payload)
        
        # 获取原始数据中对应位置的比特
        original_start = fid * original_payload_len
        original_end = original_start + payload_bit_len
        
        if original_end <= len(original_bits):
            original_payload = original_bits[original_start:original_end]
            
            # 逐位对比
            for i, (orig_bit, recv_bit) in enumerate(zip(original_payload, payload)):
                checked_bits += 1
                if orig_bit != recv_bit:
                    # 发现第一个错误位，停止计数
                    first_error_found = True
                    print(f"  [!] 第一个错误位在帧 {fid}, 偏移 {i} (总偏移 {effective_bits + i})")
                    break
                else:
                    effective_bits += 1
        else:
            # 超出原始数据范围，算作错误
            first_error_found = True
            print(f"  [!] 帧 {fid} 超出原始数据范围")
    
    # 计算实际错误比特数（用于BER）
    for fid in sorted_frame_ids:
        frame = unique_frames[fid]
        payload = frame['payload']
        payload_bit_len = len(payload)
        
        original_start = fid * original_payload_len
        original_end = original_start + payload_bit_len
        
        if original_end <= len(original_bits):
            original_payload = original_bits[original_start:original_end]
            for orig_bit, recv_bit in zip(original_payload, payload):
                if orig_bit != recv_bit:
                    actual_error_bits += 1
    
    # 9. 计算最终指标
    effective_transmission = effective_bits
    total_transmission = total_transmitted_bits
    effective_rate = effective_transmission / actual_duration_sec if actual_duration_sec > 0 else 0
    ber = (actual_error_bits / checked_bits * 100) if checked_bits > 0 else 0
    loss_rate = (marked_error_bits / total_transmission * 100) if total_transmission > 0 else 0
    
    # 10. 输出结果
    print(f"\n" + "="*60)
    print("测试结果")
    print("="*60)
    print(f"\n[传输量统计]")
    print(f"  有效传输量: {effective_transmission:,} bits ({effective_transmission/8:,.1f} bytes)")
    print(f"  总传输量:   {total_transmission:,} bits ({total_transmission/8:,.1f} bytes)")
    print(f"  检查比特数: {checked_bits:,} bits")
    print(f"  实际错误比特: {actual_error_bits:,} bits")
    print(f"  标记错误比特: {marked_error_bits:,} bits")
    
    print(f"\n[性能指标]")
    print(f"  有效传输率: {effective_rate:,.2f} bps ({effective_rate/1000:.2f} Kbps)")
    print(f"  误码率(BER): {ber:.4f}%")
    print(f"  丢失率: {loss_rate:.2f}%")
    print(f"  帧成功率: {len(valid_frames)/len(all_frames)*100:.2f}%" if all_frames else "  帧成功率: N/A")
    
    print(f"\n[数据对比]")
    print(f"  原始数据: {len(original_bits):,} bits ({len(original_data):,} bytes)")
    print(f"  解码数据: {len(decoded_bits):,} bits ({len(decoded_data):,} bytes)")
    
    return {
        'effective_bits': effective_transmission,
        'total_bits': total_transmission,
        'effective_rate_bps': effective_rate,
        'ber_percent': ber,
        'loss_rate_percent': loss_rate,
        'valid_frames': len(valid_frames),
        'total_frames': len(all_frames),
    }


def main():
    if len(sys.argv) < 4:
        print(__doc__)
        print("错误: 参数不足")
        print("用法: python test_performance.py <original.bin> <decoded.bin> <video.mp4> [duration_ms]")
        return 1
    
    original_file = sys.argv[1]
    decoded_file = sys.argv[2]
    video_path = sys.argv[3]
    duration_ms = int(sys.argv[4]) if len(sys.argv) > 4 else None
    
    # 检查文件是否存在
    for f in [original_file, decoded_file, video_path]:
        if not os.path.exists(f):
            print(f"错误: 文件不存在: {f}")
            return 1
    
    # 运行测试
    results = calculate_performance_metrics(original_file, decoded_file, video_path, duration_ms)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
