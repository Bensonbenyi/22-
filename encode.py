import cv2
import numpy as np
import sys
import os
import subprocess

if len(sys.argv) != 4:
    print("usage: encode in.bin out.mp4 duration_ms")
    sys.exit(1)

input_file = sys.argv[1]
output_video = sys.argv[2]
try:
    duration_ms = int(sys.argv[3])
except ValueError:
    print("duration_ms must be an integer")
    sys.exit(1)

# make sure input exists before processing
if not os.path.isfile(input_file):
    print(f"error: input file '{input_file}' not found")
    sys.exit(1)

fps = 30

with open(input_file, "rb") as f:
    data = f.read()

bits = []
for byte in data:
    for i in range(8):
        bits.append((byte >> (7 - i)) & 1)

total_frames = int(duration_ms / 1000 * fps)

bits = bits[:total_frames]

# prepare frames directory, clear old frames if any
if not os.path.exists("frames"):
    os.makedirs("frames")
else:
    # remove existing png files to avoid leftover frames
    for f in os.listdir("frames"):
        if f.endswith(".png"):
            try:
                os.remove(os.path.join("frames", f))
            except OSError:
                pass

width = 400
height = 400

for i, bit in enumerate(bits):

    if bit == 1:
        img = np.ones((height, width, 3), dtype=np.uint8) * 255
    else:
        img = np.zeros((height, width, 3), dtype=np.uint8)

    filename = f"frames/frame_{i:05d}.png"
    cv2.imwrite(filename, img)

cmd = f"ffmpeg -y -framerate {fps} -i frames/frame_%05d.png -c:v libx264 -pix_fmt yuv420p {output_video}"

ret = subprocess.call(cmd, shell=True)
if ret != 0:
    print(f"ffmpeg failed with exit code {ret}")
    sys.exit(ret)

print("encode finished")