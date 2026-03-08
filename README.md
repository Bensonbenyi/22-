# 二进制数据视频编解码项目

## 📋 项目简介

这是一个将**二进制文件编码成视频**，再从**视频解码恢复二进制数据**的工具集。

核心思想：
- 将二进制文件的每一位转换为图像中的像素（1 → 白色，0 → 黑色）
- 将这些图像序列编码为 MP4 视频
- 反向过程：从视频帧提取亮度信息恢复原二进制数据

这可应用于 **隐写术**、**数据冗余编码**、**创意媒体存储** 等场景。

---

## 🗂️ 文件结构

```
weblab01/
├── encode.py          # 二进制 → 视频编码器
├── decode.py          # 视频 → 二进制解码器
└── README.md          # 本文件
```

---

## 🚀 快速开始

### 1. 环境准备

**依赖**：
- Python 3.9+
- OpenCV (`opencv-python`)
- FFmpeg（视频编码/解码）

**安装依赖**：
```bash
pip install opencv-python
# ffmpeg 可通过 brew/apt/choco 等包管理器安装
brew install ffmpeg  # macOS
```

### 2. 编码：二进制文件 → MP4 视频

```bash
python encode.py <input.bin> <output.mp4> <duration_ms>
```

**参数**：
- `input.bin` — 输入的二进制文件（必须存在）
- `output.mp4` — 生成的视频文件名
- `duration_ms` — 视频时长（毫秒），整数

**示例**：
```bash
# 创建测试二进制文件
head -c 1024 /dev/urandom > in.bin

# 编码成 3 秒的视频
python encode.py in.bin output.mp4 3000
```

**输出**：
- `frames/` 目录：包含所有帧图像（`frame_00000.png`, `frame_00001.png`, ...）
- `output.mp4`：最终视频文件

---

### 3. 解码：MP4 视频 → 二进制文件

```bash
python decode.py <input.mp4> <output.bin> <valid_bits.bin>
```

**参数**：
- `input.mp4` — 来自 `encode.py` 生成的视频
- `output.bin` — 恢复的二进制输出
- `valid_bits.bin` — 有效性掩码（8 位为一组编码，哪些位可信）

**示例**：
```bash
python decode.py output.mp4 recovered.bin valid.bin
```

**输出**：
- `dframes/` 目录：提取的帧图像
- `recovered.bin`：恢复的二进制数据
- `valid.bin`：有效性信息

---

## 🔄 完整工作流

```bash
# 1. 创建输入数据
echo "Hello, World!" > message.txt

# 2. 编码成视频（2 秒）
python encode.py message.txt video.mp4 2000

# 3. 从视频解码恢复
python decode.py video.mp4 message_recovered.txt valid.bin

# 4. 比对原文件和恢复文件
cmp message.txt message_recovered.txt
echo $?  # 返回 0 表示相同，1 表示不同
```

---

## 📊 编码/解码原理

### 编码过程

1. **读取二进制文件**：逐字节读取输入文件
2. **位提取**：每字节拆分为 8 位
3. **帧生成**：
   - 每一位 → 一帧 400×400 像素图像
   - 1 → 全白（255,255,255）
   - 0 → 全黑（0,0,0）
4. **视频合成**：用 ffmpeg 以 30 FPS 将帧序列编码为 H.264 MP4

### 解码过程

1. **视频提取**：用 ffmpeg 解码 MP4，提取所有帧
2. **亮度判断**：
   - 计算每帧的平均灰度值
   - 亮度 > 128 → 1
   - 亮度 ≤ 128 → 0
3. **位合成**：8 位为一组重组成字节
4. **文件输出**：写出恢复的二进制和有效性掩码

---

## ⚙️ 配置参数

可在脚本中修改以下参数影响编码：

| 参数 | 位置 | 默认值 | 说明 |
|------|------|--------|------|
| `fps` | encode.py | 30 | 视频帧率（帧/秒） |
| `width`, `height` | encode.py | 400, 400 | 每帧图像分辨率 |
| `brightness_threshold` | decode.py | 128 | 亮度判定阈值 |
| `-c:v libx264` | encode.py | — | 视频编码器（可改为 libx265 等） |

---

## 🐛 常见问题

### Q: 运行 `encode.py` 提示 "input file not found"？
**A**: 确保输入文件存在且路径正确。可用以下命令创建测试文件：
```bash
head -c 1024 /dev/urandom > in.bin
```

### Q: ffmpeg 报错？
**A**: 检查 ffmpeg 是否安装和在 PATH 中：
```bash
which ffmpeg
ffmpeg -version
```

### Q: 解码后的文件与原文件不一致？
**A**: 这是正常的。原因可能包括：
- 视频编码/解码过程中的有损压缩或量化
- 帧提取时的颜色空间转换误差
- 亮度阈值设定不够精确

建议在重要应用中使用纠错码或增加冗余。

### Q: 如何修改视频参数（分辨率、码率等）？
**A**: 修改 `encode.py` 中的参数或 ffmpeg 命令行。例如：
```python
# 修改分辨率
width = 800
height = 800

# 或修改编码参数
cmd = f"ffmpeg -y -framerate {fps} -i frames/frame_%05d.png -c:v libx264 -crf 18 {output_video}"
```

---



## 📚 技术栈

- **Python 3.9+**: 脚本语言
- **OpenCV (cv2)**: 图像处理
- **NumPy**: 数值计算
- **FFmpeg**: 视频编码/解码
- **subprocess**: 调用外部命令

---

## 📄 许可证

无

---


*WebLab 项目*

**最后修改**: 2026 年 3 月 8 日
