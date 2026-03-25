"""
视频传输性能测试脚本
测量指标：
1. 有效传输量（bits）：在规定时长内，除去标记为错误和校验位之后的第一段正确接收位总数
                       （从第一个位开始，直到遇到第一个未被标记但实际错误的位，不包含该错误位）
2. 总传输量（bits）：在规定时长内传输（包含校验、错误标记与实际错误位）的总比特数（不含前导同步码）
3. 有效传输率（bps）：有效传输量 / 视频播放时长（秒）
4. 误码率（BER, %）：未标记错误但接收错误的比特数 ÷ 总传输量
5. 丢失率（%）：被标记为错误（不可用）的比特数 ÷ 总传输量

使用方法:
    python test_performance.py <original.bin> <video.mp4> [duration_ms]
    
示例:
    python test_performance.py input.bin transmitter_video.mp4 1000
"""

import sys
import os
import cv2

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from frame_design import (
    HEADER, HEADER_LEN, ID_LEN, LEN_FIELD_BIT, 
    PAYLOAD_LEN, CRC_LEN, FRAME_LEN, parse_frame
)


def bytes_to_bits(data_bytes):
    """将字节转换为比特字符串"""
    return ''.join(format(b, '08b') for b in data_bytes)


def extract_frames_from_video(video_path, max_video_frames=None):
    """
    从视频中提取所有帧的比特流
    返回: list of {'frame_id', 'payload', 'is_valid', 'error_type'}
    """
    from video_decode import get_matrix_from_binary, matrix_to_bits, get_matrix_from_frame_direct
    from perspective_transform import correct_frame, reset_frame_hash
    
    reset_frame_hash()
    
    cap = cv2.VideoCapture(video_path)
    all_frames = []
    frame_count = 0
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        
        frame_count += 1
        if max_video_frames and frame_count > max_video_frames:
            break
        
        # 使用透视变换
        result = correct_frame(frame)
        
        if isinstance(result, str) and result == "SKIP":
            # 被去重逻辑跳过（重复帧）- 跳过不计入统计
            continue
        elif result is not None:
            # 透视变换成功
            gray = cv2.cvtColor(result, cv2.COLOR_BGR2GRAY)
            matrix = get_matrix_from_binary(gray)
            bits = matrix_to_bits(matrix)
        else:
            # 透视变换失败
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
                # CRC 校验成功
                all_frames.append({
                    'frame_id': f_id,
                    'payload': payload,
                    'is_valid': True,
                    'error_type': None
                })
            else:
                # CRC 校验失败
                all_frames.append({
                    'frame_id': None,
                    'payload': None,
                    'is_valid': False,
                    'error_type': 'CRC_FAIL'
                })
        else:
            # 完全无法解码
            all_frames.append({
                'frame_id': None,
                'payload': None,
                'is_valid': False,
                'error_type': 'DECODE_FAIL'
            })
    
    cap.release()
    return all_frames


def calculate_performance_metrics(original_file, video_path, duration_ms=1000):
    """
    计算传输性能指标
    """
    print("="*60)
    print("视频传输性能测试")
    print("="*60)
    
    # 配置参数
    fps = 15
    frame_repeat = 1
    bits_per_frame = ID_LEN + LEN_FIELD_BIT + PAYLOAD_LEN + CRC_LEN  # 不含 HEADER
    
    # 计算指定时长内的视频帧数和数据帧数
    max_video_frames = int(duration_ms / 1000.0 * fps)
    max_data_frames = max_video_frames // frame_repeat
    
    print(f"\n[测试配置]")
    print(f"  测试时长: {duration_ms} ms")
    print(f"  帧率: {fps} FPS")
    print(f"  每帧重复: {frame_repeat} 次")
    print(f"  视频帧数: {max_video_frames}")
    print(f"  数据帧数: {max_data_frames}")
    print(f"  每帧数据量: {bits_per_frame} bits (不含HEADER)")
    
    # 读取原始数据
    with open(original_file, 'rb') as f:
        original_data = f.read()
    original_bits = bytes_to_bits(original_data)
    
    # 从视频中提取所有帧
    print(f"\n[*] 正在分析视频帧...")
    all_frames = extract_frames_from_video(video_path)
    
    # 分类统计
    valid_frames = [f for f in all_frames if f['is_valid']]
    invalid_frames = [f for f in all_frames if not f['is_valid']]
    
    # 去重（按 frame_id）
    unique_frames = {}
    for f in valid_frames:
        fid = f['frame_id']
        if fid is not None and fid not in unique_frames:
            unique_frames[fid] = f
    
    # 只保留前 max_data_frames 个帧（按 frame_id 排序）
    sorted_frame_ids = sorted(unique_frames.keys())[:max_data_frames]
    
    print(f"\n[帧统计]")
    print(f"  提取视频帧: {len(all_frames)}")
    print(f"  有效帧: {len(valid_frames)}")
    print(f"  无效帧: {len(invalid_frames)}")
    print(f"  去重后有效帧: {len(unique_frames)}")
    print(f"  测试使用帧: {len(sorted_frame_ids)} (帧ID: {sorted_frame_ids[:15]}{'...' if len(sorted_frame_ids) > 15 else ''})")
    
    # 计算总传输量（规定时长内应该传输的15帧，不含 HEADER）
    total_transmission_bits = max_data_frames * bits_per_frame
    
    # 计算丢失的比特数（规定时长内缺失的帧）
    # 实际接收到的有效帧数（去重后）vs 应该接收的帧数
    received_valid_frames = len(sorted_frame_ids)
    lost_frames = max_data_frames - received_valid_frames
    marked_error_bits = lost_frames * bits_per_frame
    
    # 计算有效传输量和错误比特数
    effective_bits = 0
    actual_error_bits = 0
    checked_bits = 0
    first_error_found = False
    
    print(f"\n[*] 正在逐帧对比...")
    
    for fid in sorted_frame_ids:
        frame = unique_frames[fid]
        payload = frame['payload']
        payload_bit_len = len(payload)
        
        # 获取原始数据中对应位置的比特
        original_start = fid * PAYLOAD_LEN
        original_end = original_start + payload_bit_len
        
        if original_end <= len(original_bits):
            original_payload = original_bits[original_start:original_end]
            
            # 逐位对比
            for i, (orig_bit, recv_bit) in enumerate(zip(original_payload, payload)):
                checked_bits += 1
                if orig_bit != recv_bit:
                    actual_error_bits += 1
                    if not first_error_found:
                        first_error_found = True
                        print(f"  [!] 第一个错误位: 帧 {fid}, 偏移 {i}")
                elif not first_error_found:
                    # 在第一个错误之前的位都是有效传输
                    effective_bits += 1
        else:
            # 超出原始数据范围
            if not first_error_found:
                first_error_found = True
                print(f"  [!] 帧 {fid} 超出原始数据范围")
    
    # 计算指标
    actual_duration_sec = duration_ms / 1000.0
    
    # 有效传输率
    effective_rate = effective_bits / actual_duration_sec if actual_duration_sec > 0 else 0
    
    # 误码率（只计算检查过的位）
    ber = (actual_error_bits / checked_bits * 100) if checked_bits > 0 else 0
    
    # 丢失率
    loss_rate = (marked_error_bits / total_transmission_bits * 100) if total_transmission_bits > 0 else 0
    
    # 输出结果
    print(f"\n" + "="*60)
    print("测试结果")
    print("="*60)
    
    print(f"\n[传输量统计]")
    print(f"  总传输量:   {total_transmission_bits:,} bits ({total_transmission_bits/8:,.1f} bytes)")
    print(f"  有效传输量: {effective_bits:,} bits ({effective_bits/8:,.1f} bytes)")
    print(f"  标记错误:   {marked_error_bits:,} bits ({marked_error_bits/8:,.1f} bytes)")
    print(f"  实际错误:   {actual_error_bits:,} bits")
    print(f"  检查位数:   {checked_bits:,} bits")
    
    print(f"\n[性能指标]")
    print(f"  有效传输率: {effective_rate:,.2f} bps ({effective_rate/1000:.2f} Kbps)")
    print(f"  误码率(BER): {ber:.4f}%")
    print(f"  丢失率: {loss_rate:.2f}%")
    print(f"  帧成功率: {len(valid_frames)/len(all_frames)*100:.2f}%" if all_frames else "  帧成功率: N/A")
    
    if not first_error_found:
        print(f"\n[✓] 测试通过：{duration_ms}ms 内无错误")
    
    return {
        'total_bits': total_transmission_bits,
        'effective_bits': effective_bits,
        'marked_error_bits': marked_error_bits,
        'actual_error_bits': actual_error_bits,
        'effective_rate_bps': effective_rate,
        'ber_percent': ber,
        'loss_rate_percent': loss_rate,
    }


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        print("错误: 参数不足")
        print("用法: python test_performance.py <original.bin> <video.mp4> [duration_ms]")
        return 1
    
    original_file = sys.argv[1]
    video_path = sys.argv[2]
    duration_ms = int(sys.argv[3]) if len(sys.argv) > 3 and sys.argv[3].isdigit() else 1000
    
    # 检查文件是否存在
    for f in [original_file, video_path]:
        if not os.path.exists(f):
            print(f"错误: 文件不存在: {f}")
            return 1
    
    # 运行测试
    results = calculate_performance_metrics(original_file, video_path, duration_ms)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
