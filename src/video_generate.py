# -*- coding: utf-8 -*-
import os
import qrcode
from PIL import Image

def frames_file_to_qrcodes(frames_file, output_dir, box_size=4, border=4):
    """
    将 encode.py 生成的帧文本文件转换为二维码图片序列。
    每个二维码存储一帧的文本内容（如 88 位二进制字符串），无额外标记。
    
    参数:
        frames_file: 帧文件路径（如 'frames_output.txt'）
        output_dir: 输出二维码图片的文件夹
        box_size: 每个模块的像素大小，默认4（保证清晰度）
        border: 边框宽度（模块数），默认4
    """
    os.makedirs(output_dir, exist_ok=True)

    # 读取帧文件，提取帧内容
    frames = []
    with open(frames_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            # 处理 "帧i: 帧内容" 格式（由 encode.py 的 save_frames 生成）
            if line.startswith('帧'):
                parts = line.split(': ', 1)
                if len(parts) == 2:
                    frames.append(parts[1])
                else:
                    print(f"警告：无法解析行: {line}")
            else:
                # 如果文件是纯帧内容（无前缀），直接添加
                frames.append(line)

    print(f"读取到 {len(frames)} 个帧，每个帧长度为 {len(frames[0]) if frames else 0} 字符")

    # 为每个帧生成二维码
    for idx, frame_data in enumerate(frames):
        # 创建二维码对象，version=None 让库自动选择最小版本以容纳数据
        qr = qrcode.QRCode(
            version=None,  # 自动选择版本
            error_correction=qrcode.constants.ERROR_CORRECT_H,  # 最高纠错等级
            box_size=box_size,
            border=border,
        )
        qr.add_data(frame_data, optimize=0)  # 直接存储原始字符串
        qr.make(fit=True)  # 自动调整版本

        img = qr.make_image(fill_color="black", back_color="white")

        # 保存图片，文件名按顺序编号
        filename = f"frame_{idx:04d}.png"
        img.save(os.path.join(output_dir, filename))
        print(f"已生成: {filename} (版本: {qr.version}, 尺寸: {img.size[0]}x{img.size[1]})")

    print(f"\n所有二维码已保存至: {output_dir}")

if __name__ == "__main__":
    # 使用示例：将 encode.py 生成的 frames_output.txt 转为二维码
    frames_file = "frames_output.txt"   # 你的帧文件
    output_dir = "./qrcodes_from_frames"
    frames_file_to_qrcodes(frames_file, output_dir, box_size=4)