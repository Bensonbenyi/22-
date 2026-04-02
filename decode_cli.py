#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
解码程序入口 - 交互式版本
双击运行，逐行提示用户输入
所有参数必须输入，不可跳过
"""

import sys
import os

# 添加 src 目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from video_decode import process_video_to_bits, save_bits_to_file, compare_files
from frame_design import PAYLOAD_LEN
from perspective_transform import reset_frame_hash

def main():
    print("=" * 60)
    print("可见光通信 - 解码程序 (VLC Decoder)")
    print("=" * 60)
    print("\n本程序从视频中解码恢复二进制文件")
    print("-" * 60)
    
    # 输入视频文件（必填）
    while True:
        print("\n请输入要解码的视频文件路径（例如: captured.mp4）：")
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
        print("\n请输入解码输出文件名（例如: output.bin）：")
        output_file = input("> ").strip().strip('"')
        
        if not output_file:
            print("错误: 输出文件名不能为空，请重新输入")
            continue
        
        break
    
    # 对比文件（必填）
    while True:
        print("\n请输入对比结果文件名（例如: vout.bin）：")
        vout_file = input("> ").strip().strip('"')
        
        if not vout_file:
            print("错误: 对比文件名不能为空，请重新输入")
            continue
        
        break
    
    # 原始文件（必填）
    while True:
        print("\n请输入原始文件路径用于对比（例如: input.bin）：")
        original_file = input("> ").strip().strip('"')
        
        if not original_file:
            print("错误: 原始文件路径不能为空，请重新输入")
            continue
        
        if not os.path.exists(original_file):
            print(f"错误: 原始文件不存在: {original_file}，请重新输入")
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
    
    print(f"\n输入视频: {input_file}")
    
    # 重置帧哈希缓存
    reset_frame_hash()
    
    # 处理视频
    print("\n[*] 正在解码视频...")
    bits = process_video_to_bits(input_file)
    
    if not bits:
        print("错误: 未能从视频中提取数据")
        input("\n按回车键退出...")
        return 1
    
    # 保存解码结果
    print(f"\n[*] 正在保存解码结果...")
    save_bits_to_file(bits, output_file, max_frame_id=None)
    
    print(f"\n[*] 解码完成，输出: {output_file}")
    
    # 生成对比文件
    print(f"\n[*] 正在生成对比文件...")
    print(f"    原始文件: {original_file}")
    print(f"    对比文件: {vout_file}")
    
    # 计算需要比较的数据量
    fps = 15
    frame_repeat = 1
    payload_bytes = PAYLOAD_LEN // 8
    max_frames = int(duration_ms / 1000.0 * fps / frame_repeat)
    expected_bytes = max_frames * payload_bytes
    print(f"[*] 指定时长：{duration_ms} ms, 预期数据：{expected_bytes} bytes")
    compare_files(output_file, original_file, vout_file, limit_bytes=expected_bytes)
    
    print(f"[*] 对比文件已生成: {vout_file}")
    
    print("\n" + "=" * 60)
    print("[+] 解码完成!")
    print("=" * 60)
    print(f"    输出文件: {output_file}")
    print(f"    对比文件: {vout_file}")
    print("=" * 60)
    
    input("\n按回车键退出...")
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()
        input("\n按回车键退出...")
        sys.exit(1)
