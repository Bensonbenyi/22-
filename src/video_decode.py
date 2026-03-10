"""
video_decode.py

Extract frames from QR video and recover frame bits
"""

import cv2
import numpy as np
from decode import decode_frames

QR_SIZE = 16
MODULE_SIZE = 20
IMG_SIZE = QR_SIZE * MODULE_SIZE


def extract_frames(video_path):
    """
    Extract all frames from video
    """
    cap = cv2.VideoCapture(video_path)

    frames = []

    while True:
        ret, frame = cap.read()

        if not ret:
            break

        frames.append(frame)

    cap.release()

    return frames


def preprocess(frame):
    """
    Convert frame to grayscale and binary
    """

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    _, binary = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY)

    return binary


def detect_qr_matrix(image):
    """
    Sample pixels to recover 16x16 matrix
    Skip finder pattern area (bottom-right 7x7)
    """

    matrix = np.zeros((QR_SIZE, QR_SIZE), dtype=int)

    finder_size = 7
    finder_offset = QR_SIZE - finder_size

    for i in range(QR_SIZE):
        for j in range(QR_SIZE):

            if i >= finder_offset and j >= finder_offset:
                continue

            y = int((i + 0.5) * MODULE_SIZE)
            x = int((j + 0.5) * MODULE_SIZE)

            pixel = image[y, x]

            if pixel < 128:
                matrix[i][j] = 1
            else:
                matrix[i][j] = 0

    return matrix


def matrix_to_bits(matrix):
    """
    Convert matrix back to bit string
    Only first 88 bits are used
    """

    bits = ""

    for i in range(QR_SIZE):
        for j in range(QR_SIZE):

            bits += str(matrix[i][j])

    return bits[:88]


def decode_video(video_path):
    """
    Convert video frames into frame bits
    """

    frames = extract_frames(video_path)

    frames_bits = []

    for frame in frames:

        binary = preprocess(frame)

        matrix = detect_qr_matrix(binary)

        bits = matrix_to_bits(matrix)

        frames_bits.append(bits)

    return frames_bits


def main():

    frame_bits = decode_video("out.mp4")

    print("Frames detected:", len(frame_bits))

    decode_frames(frame_bits, "vout.bin")

    print("Recovered file: vout.bin")


if __name__ == "__main__":
    main()