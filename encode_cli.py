#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
编码程序入口 - 交互式版本
双击运行，逐行提示用户输入
所有参数必须输入，不可跳过
"""

import sys
import os

# 添加 src 目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from encode import encode_file
from video_generate import generate_video
from frame_design import PAYLOAD_LEN

def main():
    print("=" * 60)
    print("可见光通信 - 编码程序 (VLC Encoder)")
    print("=" * 60)
    print("\n本程序将二进制文件编码为二维码视频")
    print("-" * 60)
    
    # 交互式输入 - 输入文件（必填）
    while True:
        print("\n请输入要编码的文件路径（例如: input.bin）：")
        input_file = input("> ").strip().strip('"')
        
        if not input_file:
            print("错误: 文件路径不能为空，请重新输入")
            continue
        
        if not os.path.exists(input_file):
            print(f"错误: 文件不存在: {input_file}，请重新输入")
            continue
        
        break
    
    # 输出文件（必填）
    while True:
        print("\n请输入输出视频文件名（例如: output.mp4）：")
        output_file = input("> ").strip().strip('"')
        
        if not output_file:
            print("错误: 输出文件名不能为空，请重新输入")
            continue
        
        break
    
    # 时长（必填）
    while True:
        print("\n请输入视频时长限制（毫秒，例如: 1000）：")
        duration_input = input("> ").strip()
        
        if not duration_input:
            print("错误: 时长不能为空，请重新输入")
            continue
        
        try:
            duration_ms = int(duration_input)
            if duration_ms <= 0:
                print("错误: 时长必须大于0，请重新输入")
                continue
            break
        except ValueError:
            print("错误: 时长必须是数字，请重新输入")
            continue
    
    # 获取文件大小
    file_size = os.path.getsize(input_file)
    print(f"\n输入文件: {input_file} ({file_size} bytes)")
    
    # 编码生成帧
    print("\n[*] 正在编码...")
    frames = encode_file(input_file)
    
    if not frames:
        print("错误: 编码失败")
        input("\n按回车键退出...")
        return 1
    
    # 使用默认帧率 15 FPS
    fps = 15
    frame_repeat = 1
    
    # 计算总帧数和视频时长
    total_frame_count = len(frames)
    
    # 用户指定了时长
    target_duration_sec = duration_ms / 1000.0
    max_frames_needed = int(target_duration_sec * fps / frame_repeat)
    while max_frames_needed > 0 and (max_frames_needed * frame_repeat / fps) > target_duration_sec:
        max_frames_needed -= 1
    frames = frames[:max_frames_needed]
    actual_duration_sec = len(frames) * frame_repeat / fps
    
    print(f"\n[*] 指定视频时长: {duration_ms} ms")
    print(f"[*] 原始帧数: {total_frame_count}, 截取后帧数: {len(frames)}")
    print(f"[*] 实际视频时长: {actual_duration_sec*1000:.0f} ms")
    
    # 生成视频
    print(f"\n[*] 正在生成视频...")
    generate_video(frames, output_file, fps=fps)
    
    actual_duration = len(frames) * frame_repeat / fps
    print(f"\n" + "=" * 60)
    print("[+] 编码完成!")
    print("=" * 60)
    print(f"    输出文件: {output_file}")
    print(f"    帧数: {len(frames)}")
    print(f"    帧率: {fps} FPS")
    print(f"    视频时长: ~{actual_duration*1000:.0f} ms")
    print("=" * 60)
    
    input("\n按回车键退出...")
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"\n错误: {e}")
        input("\n按回车键退出...")
        sys.exit(1)
