import numpy as np
import cv2


def frame_to_qr(frame_bits):
    """
    将88bit frame转换为16x16矩阵
    :param frame_bits: 01字符串
    :return: 16x16 numpy矩阵
    """

    # 将字符串转换为0/1列表
    bits = [int(b) for b in frame_bits]

    # 16x16需要256bit，不够补0
    if len(bits) < 256:
        bits += [0] * (256 - len(bits))

    # 变成16x16矩阵
    matrix = np.array(bits[:256]).reshape((16, 16))

    return matrix


def generate_frame_image(frame_bits, scale=20):
    """
    根据frame生成二维码图片
    """

    matrix = frame_to_qr(frame_bits)

    # 1 -> 黑色 0 -> 白色
    img = np.where(matrix == 1, 0, 255).astype(np.uint8)

    # 放大
    img = cv2.resize(
        img,
        (16 * scale, 16 * scale),
        interpolation=cv2.INTER_NEAREST
    )

    return img


def generate_video(frames, output_path="output_video.mp4", fps=5):
    """
    将多帧二维码生成视频
    """

    images = []

    for frame in frames:
        img = generate_frame_image(frame)
        images.append(img)

    height, width = images[0].shape

    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    video = cv2.VideoWriter(output_path, fourcc, fps, (width, height), False)

    for img in images:
        video.write(img)

    video.release()

    print("视频生成完成:", output_path)


if __name__ == "__main__":

    # 示例frame
    frames = [
        "1010101010101010101010101010101010101010101010101010101010101010101010101010101010101010",
        "0101010101010101010101010101010101010101010101010101010101010101010101010101010101010101"
    ]

    generate_video(frames)