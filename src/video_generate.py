"""
video_generate.py - 视觉发送核心模块 (Visual Transmitter)

功能描述:
    本模块负责将编码后的 01 比特流帧 (Bit-frames) 转化为物理可视的图像信号。
    它采用 41x41 的自定义二维码矩阵结构，并集成了 L-Sign 定位系统。

核心逻辑:
    1. 矩阵映射: 将 1312 bits 的帧数据映射到 41x41 的 Numpy 矩阵中。
    2. 定位符绘制: 在矩阵的三个角绘制 7x7 '回'字形定位符，右下角绘制方向标识块。
    3. 图像增强: 使用 INTER_NEAREST 插值放大像素，并添加白色保护带 (Quiet Zone)。
    4. 视频合成: 调用 OpenCV VideoWriter 将图像序列封装为 .mp4 格式。

参数规范:
    - QR_SIZE: 41 (矩阵规格)
    - Scale: 15 (单格像素缩放倍化)
    - FPS: 建议 10-15 (适配手机快门同步)

协作说明:
    输入接口: 接受由 encode.py 产生的 frame_bits 列表。
    输出接口: 在指定路径生成用于播放传输的视频文件。
"""
import os
import numpy as np
import random
import cv2
from encode import encode_file

# 根据之前的设计，总格子数为 41x41
QR_SIZE = 41 

def frame_to_qr(frame_bits):
    """
    将 frame_bits 转换为 41x41 矩阵，带定位符
    """
    # 1. 初始化全白矩阵 (0表示白色，1表示黑色，方便后续 np.where 处理)
    matrix = np.zeros((QR_SIZE, QR_SIZE), dtype=np.uint8)

    # 2. 定义绘制定位符的内部函数 (7x7 回字形)
    def draw_finder(m, x, y):
        m[x:x+7, y:y+7] = 1        # 外层黑块
        m[x+1:x+6, y+1:y+6] = 0    # 中层白块
        m[x+2:x+5, y+2:y+5] = 1    # 内层黑块

    # 3. 绘制三个角的定位符
    draw_finder(matrix, 0, 0)                  # 左上
    draw_finder(matrix, 0, QR_SIZE - 7)         # 右上
    draw_finder(matrix, QR_SIZE - 7, 0)         # 左下

    # 4. 绘制右下角的方向标 (3x3 实心黑块，用于区分方向)
    rx, ry = QR_SIZE - 8, QR_SIZE - 8
    matrix[rx:rx+5, ry:ry+5] = 1               # 5x5 黑框
    matrix[rx+1:rx+4, ry+1:ry+4] = 0           # 3x3 白框
    matrix[rx+2, ry+2] = 1                     # 中心 1x1 黑点

    # 5. 提取可填充数据的区域 (遮罩 Mask)
    # 创建一个和 matrix 一样大的布尔矩阵，标记哪里可以填数据
    data_mask = np.ones((QR_SIZE, QR_SIZE), dtype=bool)
    # 扣除左上、右上、左下三个 7x7 区域
    data_mask[0:7, 0:7] = False
    data_mask[0:7, QR_SIZE-7:QR_SIZE] = False
    data_mask[QR_SIZE-7:QR_SIZE, 0:7] = False
    # 扣除右下角方向标区域
    data_mask[rx:rx+5, ry:ry+5] = False

    # 6. 填充 frame_bits 到数据区
    bits = [int(b) for b in frame_bits]
    
    # 找到所有为 True 的索引坐标
    available_coords = np.argwhere(data_mask)
    
    # 如果比特数不够，补0；如果太多，截断
    max_data_len = len(available_coords)

    # 重点：先用随机数铺满整个背景，再把真实数据覆盖上去
    # 这样哪怕数据只有一半，剩下的一半也是随机噪点
    full_random_bits = [random.randint(0, 1) for _ in range(max_data_len)]
    data_to_fill_len = min(len(bits), max_data_len)

    for i in range(data_to_fill_len):
        full_random_bits[i] = bits[i]
    
    for i in range(max_data_len):
        r, c = available_coords[i]
        matrix[r, c] = full_random_bits[i]

    return matrix

def generate_frame_image(frame_bits, scale=15):
    """
    根据 frame 生成二维码图片，增加白色边框（Quiet Zone）
    """
    matrix = frame_to_qr(frame_bits)

    # 1 -> 黑色 (0), 0 -> 白色 (255)
    img = np.where(matrix == 1, 0, 255).astype(np.uint8)

    # 放大：使用 INTER_NEAREST 保持像素方块清晰
    img_resized = cv2.resize(
        img,
        (QR_SIZE * scale, QR_SIZE * scale),
        interpolation=cv2.INTER_NEAREST
    )
    
    # 增加白色边框（Quiet Zone），方便手机定位，四周增加 2 个格子的宽度
    border = 2 * scale
    img_with_border = cv2.copyMakeBorder(
        img_resized, 
        border, border, border, border, 
        cv2.BORDER_CONSTANT, 
        value=255
    )

    return img_with_border

def generate_video(frames, output_path="output_video.mp4", fps=10):
    """
    将多帧二维码生成视频
    """
    images = []
    for frame in frames:
        img = generate_frame_image(frame)
        images.append(img)

    # 修正：因为增加了边框，需要重新获取宽高
    height, width = images[0].shape

    # 注意：cv2.VideoWriter 默认需要 (width, height)
    # 并且如果保存灰度图，最后一个参数 isColor 必须设为 False
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    video = cv2.VideoWriter(output_path, fourcc, fps, (width, height), False)

    for img in images:
        # 重复写入同一帧 2 次（增加视频冗余度，方便手机捕捉）
        video.write(img)
        video.write(img)

    video.release()
    print(f"视频生成完成: {output_path}，当前分辨率: {width}x{height}")

if __name__ == "__main__":
    # 1. 配置参数
    INPUT_BIN_FILE = "input.bin" 
    OUTPUT_VIDEO_FILE = "transmitter_video.mp4"
    TRANSMIT_FPS = 10 

    print("="*50)
    print("可见光通信 - 发送端启动")
    print("="*50)

    # 2. 检查并准备输入文件
    if not os.path.exists(INPUT_BIN_FILE):
        with open(INPUT_BIN_FILE, "wb") as f:
            # 产生 1KB 随机数据用于演示
            f.write(os.urandom(1024))
        print(f"[*] 未找到输入文件，已自动创建测试文件: {INPUT_BIN_FILE}")

    # 3. 调用 encode.py 中的逻辑生成帧序列
    print(f"[*] 正在读取文件并进行数据分帧...")
    data_frames = encode_file(INPUT_BIN_FILE)

    if not data_frames:
        print("错误：未能生成有效帧，请检查输入文件。")
    else:
        # 4. 调用本文件中的函数生成视频
        print(f"[*] 正在将 {len(data_frames)} 个数据帧转换为可视信号...")
        generate_video(data_frames, OUTPUT_VIDEO_FILE, fps=TRANSMIT_FPS)
        
        print("\n" + "="*50)
        print(f"发送视频生成成功！")
        print(f"文件路径: {os.path.abspath(OUTPUT_VIDEO_FILE)}")
        print(f"传输帧数: {len(data_frames)} 帧")
        print("="*50)