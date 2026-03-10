import numpy as np
import cv2

# 根据之前的设计，总格子数为 41x41
QR_SIZE = 41 

def frame_to_qr(frame_bits):
    """
    将 frame_bits 转换为 41x41 矩阵，带定位符
    :param frame_bits: 01字符串 (长度应适配 41x41 扣除定位符后的空间)
    :return: 41x41 numpy矩阵
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
    matrix[QR_SIZE - 5:QR_SIZE - 2, QR_SIZE - 5:QR_SIZE - 2] = 1

    # 5. 提取可填充数据的区域 (遮罩 Mask)
    # 创建一个和 matrix 一样大的布尔矩阵，标记哪里可以填数据
    data_mask = np.ones((QR_SIZE, QR_SIZE), dtype=bool)
    # 扣除左上、右上、左下三个 7x7 区域
    data_mask[0:7, 0:7] = False
    data_mask[0:7, QR_SIZE-7:QR_SIZE] = False
    data_mask[QR_SIZE-7:QR_SIZE, 0:7] = False
    # 扣除右下角方向标区域
    data_mask[QR_SIZE-5:QR_SIZE-2, QR_SIZE-5:QR_SIZE-2] = False

    # 6. 填充 frame_bits 到数据区
    bits = [int(b) for b in frame_bits]
    
    # 找到所有为 True 的索引坐标
    available_coords = np.argwhere(data_mask)
    
    # 如果比特数不够，补0；如果太多，截断
    max_data_len = len(available_coords)
    if len(bits) < max_data_len:
        bits += [0] * (max_data_len - len(bits))
    
    for i in range(max_data_len):
        r, c = available_coords[i]
        matrix[r, c] = bits[i]

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
    # 按照 41x41 设计，可容纳约 1400+ bit
    # 测试时可以传一个长字符串
    test_bits = "101101" * 300 
    frames = [test_bits, test_bits[::-1]] # 两个反向的帧

    generate_video(frames)