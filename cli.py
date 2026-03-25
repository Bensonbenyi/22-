"""
可见光通信系统 - 命令行接口 (CLI)

使用方法:
    编码: python cli.py encode <input.bin> <output.mp4> [duration_ms]
          例如: python cli.py encode input.bin out.mp4 5000
          
    解码: python cli.py decode <input.mp4> <output.bin> [vout.bin] [duration_ms]
          例如: python cli.py decode transmitter_video.mp4 out.bin vout.bin 5000

参数说明:
    encode:
        input.bin    - 输入的二进制文件
        output.mp4   - 输出的视频文件
        duration_ms  - 视频时长(毫秒), 只截取前duration_ms的数据, 可选
        
    decode:
        input.mp4    - 输入的视频文件(手机拍摄)
        output.bin   - 解码输出的二进制文件
        vout.bin     - 对比结果文件(可选)
        duration_ms  - 视频时长(毫秒), 只比较前duration_ms对应的数据量, 可选
"""

import sys
import os
import argparse

# 添加 src 目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from encode import encode_file
from video_decode import process_video_to_bits, save_bits_to_file, compare_files
from frame_design import PAYLOAD_LEN
from perspective_transform import reset_frame_hash


def encode_command(args):
    """编码命令: 将二进制文件转换为视频
    
    如果指定了 duration_ms, 则只生成前 duration_ms 毫秒的视频
    (保持默认帧率 10 FPS, 只截取前面的帧)
    """
    input_file = args.input
    output_file = args.output
    duration_ms = args.duration
    
    # 检查输入文件
    if not os.path.exists(input_file):
        print(f"错误: 输入文件不存在: {input_file}")
        return 1
    
    # 获取文件大小
    file_size = os.path.getsize(input_file)
    print(f"输入文件: {input_file} ({file_size} bytes)")
    
    # 编码生成帧
    print("\n[*] 正在编码...")
    frames = encode_file(input_file)
    
    if not frames:
        print("错误: 编码失败")
        return 1
    
    # 使用默认帧率 15 FPS
    fps = 15
    frame_repeat = 1  # 每帧放1次
    
    # 计算总帧数和视频时长
    total_frame_count = len(frames)
    total_duration_sec = total_frame_count * frame_repeat / fps
    
    if duration_ms:
        # 用户指定了时长(毫秒), 只截取前面的帧
        # 计算需要多少帧：帧数 = 时长(ms) / 1000 * fps / frame_repeat
        # 使用向下取整确保不超过指定时长
        target_duration_sec = duration_ms / 1000.0
        # 计算最大帧数（向下取整，确保不超过时长）
        max_frames_needed = int(target_duration_sec * fps / frame_repeat)
        # 如果计算结果导致时长超过目标，减少一帧
        while max_frames_needed > 0 and (max_frames_needed * frame_repeat / fps) > target_duration_sec:
            max_frames_needed -= 1
        # 截取前面的帧
        frames = frames[:max_frames_needed]
        actual_duration_sec = len(frames) * frame_repeat / fps
        print(f"\n[*] 指定视频时长: {duration_ms} ms")
        print(f"[*] 原始帧数: {total_frame_count}, 截取后帧数: {len(frames)}")
        print(f"[*] 实际视频时长: {actual_duration_sec*1000:.0f} ms ({actual_duration_sec*1000/target_duration_sec*100:.1f}%)")
    else:
        # 使用全部帧
        print(f"\n[*] 使用默认帧率: {fps} FPS")
        print(f"[*] 总帧数: {total_frame_count}")
        print(f"[*] 预计视频时长: {total_duration_sec*1000:.0f} ms")
    
    # 导入 video_generate 模块
    from video_generate import generate_video
    
    # 生成视频
    print(f"\n[*] 正在生成视频...")
    generate_video(frames, output_file, fps=fps)
    
    actual_duration = len(frames) * frame_repeat / fps
    print(f"\n[+] 编码完成!")
    print(f"    输出文件: {output_file}")
    print(f"    帧数: {len(frames)}")
    print(f"    帧率: {fps} FPS")
    print(f"    视频时长: ~{actual_duration*1000:.0f} ms")
    
    return 0


def decode_command(args):
    """解码命令: 将视频解码为二进制文件
    
    如果指定了 duration_ms, 则只比较前 duration_ms 对应的数据量
    """
    input_file = args.input
    output_file = args.output
    vout_file = args.vout
    duration_ms = args.duration
    
    # 检查输入文件
    if not os.path.exists(input_file):
        print(f"错误: 输入视频不存在: {input_file}")
        return 1
    
    print(f"输入视频: {input_file}")
    
    # 重置帧哈希缓存
    reset_frame_hash()
    
    # 处理视频
    print("\n[*] 正在解码视频...")
    bits = process_video_to_bits(input_file)
    
    if not bits:
        print("错误: 未能从视频中提取数据")
        return 1
    
    # 保存解码结果
    print(f"\n[*] 正在保存解码结果...")
    save_bits_to_file(bits, output_file, max_frame_id=None)
    
    print(f"\n[+] 解码完成!")
    print(f"    输出文件: {output_file}")
    
    # 如果提供了 vout 参数, 进行对比
    if vout_file:
        # 尝试找到原始文件进行对比
        original_file = "input.bin"  # 默认原始文件
        if os.path.exists(original_file):
            print(f"\n[*] 正在对比文件...")
            
            # 计算需要比较的数据量
            if duration_ms:
                # 根据时长计算应该传输多少数据
                fps = 15
                frame_repeat = 1
                payload_bytes = PAYLOAD_LEN // 8
                # 计算帧数
                max_frames = int(duration_ms / 1000.0 * fps / frame_repeat)
                # 计算数据量
                expected_bytes = max_frames * payload_bytes
                print(f"[*] 指定时长: {duration_ms} ms, 预期数据: {expected_bytes} bytes")
                
                # 只比较前 expected_bytes
                compare_files(output_file, original_file, vout_file, limit_bytes=expected_bytes)
            else:
                # 没有指定时长, 比较全部
                compare_files(output_file, original_file, vout_file)
        else:
            print(f"[!] 警告: 未找到原始文件 {original_file}, 跳过对比")
    
    return 0


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="可见光通信系统 - 命令行接口",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  编码: python cli.py encode input.bin out.mp4 5000
  解码: python cli.py decode transmitter_video.mp4 out.bin vout.bin 5000
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='可用命令')
    
    # 编码命令
    encode_parser = subparsers.add_parser('encode', help='将二进制文件编码为视频')
    encode_parser.add_argument('input', help='输入的二进制文件')
    encode_parser.add_argument('output', help='输出的视频文件')
    encode_parser.add_argument('duration', type=int, nargs='?', default=None,
                              help='视频时长(毫秒), 可选')
    
    # 解码命令
    decode_parser = subparsers.add_parser('decode', help='将视频解码为二进制文件')
    decode_parser.add_argument('input', help='输入的视频文件')
    decode_parser.add_argument('output', help='输出的二进制文件')
    decode_parser.add_argument('vout', nargs='?', default=None,
                              help='对比结果文件(可选)')
    decode_parser.add_argument('duration', type=int, nargs='?', default=None,
                              help='视频时长(毫秒), 用于限制对比数据量, 可选')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    if args.command == 'encode':
        return encode_command(args)
    elif args.command == 'decode':
        return decode_command(args)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
