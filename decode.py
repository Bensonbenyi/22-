import cv2
import numpy as np
import sys
import subprocess
import os

if len(sys.argv) != 4:
    print("usage: decode in.mp4 out.bin vout.bin")
    exit()

input_video = sys.argv[1]
out_bin = sys.argv[2]
vout_bin = sys.argv[3]

if not os.path.exists("dframes"):
    os.makedirs("dframes")

cmd = f"ffmpeg -y -i {input_video} dframes/frame_%05d.png"
subprocess.call(cmd, shell=True)

files = sorted(os.listdir("dframes"))

bits = []
valid = []

for f in files:

    path = os.path.join("dframes", f)

    img = cv2.imread(path)

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    brightness = np.mean(gray)

    if brightness > 128:
        bits.append(1)
    else:
        bits.append(0)

    valid.append(1)

bytes_out = []

for i in range(0, len(bits), 8):

    byte = 0

    for j in range(8):

        if i + j < len(bits):
            byte = (byte << 1) | bits[i + j]

    bytes_out.append(byte)

with open(out_bin, "wb") as f:
    f.write(bytearray(bytes_out))

valid_bytes = []

for i in range(0, len(valid), 8):

    byte = 0

    for j in range(8):

        if i + j < len(valid) and valid[i + j]:
            byte |= (1 << (7 - j))

    valid_bytes.append(byte)

with open(vout_bin, "wb") as f:
    f.write(bytearray(valid_bytes))

print("decode finished")