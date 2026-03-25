"""
video_generate.py

功能描述:
    本模块负责将编码后的 01 比特流帧 (Bit-frames) 转化为物理可视的图像信号。
    适配 1920x1080 分辨率，使用 11x11 大定位点，便于手机拍摄识别。
    【无白边版本】二维码直接占满整个 1920x1080 画面

核心逻辑:
    1. 矩阵映射: 将帧数据映射到 128x72 的 Numpy 矩阵中。
    2. 定位符绘制: 在矩阵的四个角绘制 11x11 大定位符。
    3. 视频合成: 调用 OpenCV VideoWriter 将图像序列封装为 .mp4 格式。

参数规范:
    - QR_WIDTH: 128 (水平矩阵规格)
    - QR_HEIGHT: 72 (垂直矩阵规格)
    - CELL_SIZE: 15 (单格像素大小)
    - FINDER_SIZE: 11 (大定位点，便于检测)
    - VIDEO_WIDTH: 1920 (视频宽度)
    - VIDEO_HEIGHT: 1080 (视频高度)
    - FPS: 10-15 (适配手机快门同步)
"""
import os
import numpy as np
import random
import cv2
from encode import encode_file
from frame_design import (
    QR_WIDTH, QR_HEIGHT, FINDER_SIZE, 
    VIDEO_WIDTH, VIDEO_HEIGHT, CELL_SIZE, BORDER_CELLS
)

def frame_to_qr(frame_bits):
    """
    将 frame_bits 转换为 128x72 矩阵，带 11x11 大定位符
    【无白边版本】
    """
    # 1. 初始化全白矩阵 (0表示白色，1表示黑色)
    matrix = np.zeros((QR_HEIGHT, QR_WIDTH), dtype=np.uint8)

    # 2. 定义绘制定位符的内部函数 (11x11 大回字形)
    def draw_finder(m, x, y):
        # 外层黑框 (11x11)
        m[x:x+FINDER_SIZE, y:y+FINDER_SIZE] = 1
        # 中层白框 (9x9)
        m[x+1:x+FINDER_SIZE-1, y+1:y+FINDER_SIZE-1] = 0
        # 内层黑框 (7x7)
        m[x+2:x+FINDER_SIZE-2, y+2:y+FINDER_SIZE-2] = 1
        # 中心白点 (5x5)
        m[x+3:x+FINDER_SIZE-3, y+3:y+FINDER_SIZE-3] = 0
        # 最中心黑点 (3x3)
        m[x+4:x+FINDER_SIZE-4, y+4:y+FINDER_SIZE-4] = 1

    # 3. 绘制四个角的定位符（11x11 大定位符）
    draw_finder(matrix, 0, 0)                                    # 左上
    draw_finder(matrix, 0, QR_WIDTH - FINDER_SIZE)               # 右上
    draw_finder(matrix, QR_HEIGHT - FINDER_SIZE, 0)              # 左下
    draw_finder(matrix, QR_HEIGHT - FINDER_SIZE, QR_WIDTH - FINDER_SIZE)  # 右下

    # 4. 提取可填充数据的区域 (遮罩 Mask) 
    data_mask = np.ones((QR_HEIGHT, QR_WIDTH), dtype=bool)
    # 扣除四个角的 11x11 定位符区域
    data_mask[0:FINDER_SIZE, 0:FINDER_SIZE] = False
    data_mask[0:FINDER_SIZE, QR_WIDTH-FINDER_SIZE:QR_WIDTH] = False
    data_mask[QR_HEIGHT-FINDER_SIZE:QR_HEIGHT, 0:FINDER_SIZE] = False
    data_mask[QR_HEIGHT-FINDER_SIZE:QR_HEIGHT, QR_WIDTH-FINDER_SIZE:QR_WIDTH] = False

    # 5. 填充 frame_bits 到数据区
    bits = [int(b) for b in frame_bits]
    
    # 找到所有为 True 的索引坐标
    available_coords = np.argwhere(data_mask)
    
    # 如果比特数不够，补0；如果太多，截断
    max_data_len = len(available_coords)

    # 先用随机数铺满整个背景，再把真实数据覆盖上去
    full_random_bits = [random.randint(0, 1) for _ in range(max_data_len)]
    data_to_fill_len = min(len(bits), max_data_len)

    for i in range(data_to_fill_len):
        full_random_bits[i] = bits[i]
    
    for i in range(max_data_len):
        r, c = available_coords[i]
        matrix[r, c] = full_random_bits[i]

    return matrix

def generate_frame_image(frame_bits, cell_size=CELL_SIZE):
    """
    根据 frame 生成二维码图片，适配 1920x1080 分辨率
    【无白边版本】二维码直接占满整个画面
    """
    matrix = frame_to_qr(frame_bits)

    # 1 -> 黑色 (0), 0 -> 白色 (255)
    img = np.where(matrix == 1, 0, 255).astype(np.uint8)

    # 放大到指定像素大小（直接就是 1920x1080，无白边）
    img_resized = cv2.resize(
        img,
        (VIDEO_WIDTH, VIDEO_HEIGHT),  # 直接输出 1920x1080
        interpolation=cv2.INTER_NEAREST
    )
    
    # 【无白边】不再添加边框
    return img_resized

def generate_video(frames, output_path="transmitter_video.mp4", fps=15):
    """
    将多帧二维码生成视频，分辨率 1920x1080
    【无白边版本】
    """
    images = []
    for frame in frames:
        img = generate_frame_image(frame)
        images.append(img)

    # 获取宽高（应该是 1920x1080）
    height, width = images[0].shape

    # cv2.VideoWriter 需要 (width, height)
    # 保存灰度图，isColor 设为 False
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    video = cv2.VideoWriter(output_path, fourcc, fps, (width, height), False)

    for img in images:
        # 写入一帧
        video.write(img)

    video.release()
    print(f"视频生成完成: {output_path}，分辨率: {width}x{height}")

if __name__ == "__main__":
    # 1. 配置参数
    INPUT_BIN_FILE = "input.bin" 
    OUTPUT_VIDEO_FILE = "transmitter_video.mp4"
    TRANSMIT_FPS = 15 

    print("="*50)
    print("可见光通信 - 发送端启动 (1920x1080, 无白边)")
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
        
        # 计算实际视频信息
        frame_repeat = 2  # 每帧重复次数
        video_frames = len(data_frames) * frame_repeat  # 实际视频帧数
        duration_sec = video_frames / TRANSMIT_FPS
        
        print("\n" + "="*50)
        print(f"发送视频生成成功！")
        print(f"文件路径: {os.path.abspath(OUTPUT_VIDEO_FILE)}")
        print(f"传输帧数: {len(data_frames)} 帧")
        print(f"分辨率: {VIDEO_WIDTH}x{VIDEO_HEIGHT}")
        print(f"矩阵大小: {QR_WIDTH}x{QR_HEIGHT}")
        print(f"定位点大小: {FINDER_SIZE}x{FINDER_SIZE}")
        print(f"白边: 无")
        print("="*50)
