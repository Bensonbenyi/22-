# 可见光通信系统 - 二进制数据视频编解码

## 📋 项目简介

这是一个基于二维码视频的**可见光通信系统**，可将二进制文件编码为视频，再通过拍摄视频解码恢复数据。

**核心特性**：
- **高分辨率**：1920×1080 视频，128×72 数据矩阵
- **大定位点**：11×11 回字形定位符，便于手机拍摄识别
- **无白边设计**：二维码占满整个画面，最大化数据密度
- **帧重复机制**：每帧重复播放，提高识别率
- **CRC 校验**：16位 CRC 保证数据完整性
- **命令行接口**：支持编码/解码/性能测试

**应用场景**：
- 可见光通信（VLC）
- 离线数据传输
- 创意媒体存储
- 二维码视频传输

---

## 🗂️ 文件结构

```
project/
├── src/
│   ├── encode.py              # 编码核心：文件 → 比特流 → 帧序列
│   ├── frame_design.py        # 帧结构设计：HEADER + FRAME_ID + DATA_LEN + PAYLOAD + CRC
│   ├── video_generate.py      # 视频生成：帧 → 二维码图像 → MP4
│   ├── video_decode.py        # 视频解码：MP4 → 帧提取 → 透视变换 → 比特流
│   └── perspective_transform.py  # 透视变换：4点定位与图像纠正
├── cli.py                     # 命令行接口（CLI）
├── test_performance.py        # 性能测试工具
├── input.bin                  # 待编码的二进制输入文件
├── transmitter_video.mp4      # 编码生成的视频输出文件
├── out.bin                    # 解码输出的二进制文件
└── vout.bin                   # 逐字节对比结果文件（0xff=正确，其他=错误）
```

---

## 🚀 快速开始

### 1. 环境准备

**依赖**：
- Python 3.9+
- OpenCV (`opencv-python`)
- NumPy (`numpy`)

**安装依赖**：
```bash
pip install opencv-python numpy
```

---

### 2. 命令行接口（CLI）

#### 编码：二进制文件 → MP4 视频

```bash
python cli.py encode <input.bin> <output.mp4> [duration_ms]
```

**示例**：
```bash
# 编码整个文件
python cli.py encode input.bin out.mp4

# 只编码前 1000ms 的数据
python cli.py encode input.bin out.mp4 1000
```

**参数**：
- `input.bin` - 输入的二进制文件
- `output.mp4` - 输出的视频文件
- `duration_ms` - 视频时长（毫秒），可选

**输出信息**：
- 数据帧数、视频时长、帧率
- 默认配置：15 FPS，每帧播放 1 次

---

#### 解码：MP4 视频 → 二进制文件

```bash
python cli.py decode <input.mp4> <output.bin> [vout.bin] [duration_ms]
```

**示例**：
```bash
# 基础解码
python cli.py decode transmitter_video.mp4 out.bin

# 解码并对比原始文件
python cli.py decode transmitter_video.mp4 out.bin vout.bin

# 只对比前 1000ms 的数据
python cli.py decode transmitter_video.mp4 out.bin vout.bin 1000
```

**参数**：
- `input.mp4` - 输入的视频文件（手机拍摄）
- `output.bin` - 解码输出的二进制文件
- `vout.bin` - 对比结果文件，可选
- `duration_ms` - 限制对比时长（毫秒），可选

**输出信息**：
- 总帧数、成功提取帧数
- 解析统计（成功/失败/跳过）
- 恢复帧数
- 准确率（如果提供 vout 参数）

---

### 3. 性能测试

```bash
python test_performance.py <original.bin> <decoded.bin> <video.mp4> [duration_ms]
```

**示例**：
```bash
python test_performance.py input.bin out.bin transmitter_video.mp4 1000
```

**测量指标**：

| 指标 | 说明 |
|------|------|
| **有效传输量** | 从第一个位开始，直到遇到第一个错误位的正确接收位数 |
| **总传输量** | 规定时长内传输的总比特数（不含前导同步码） |
| **有效传输率** | 有效传输量 ÷ 视频播放时长（bps） |
| **误码率（BER）** | 未标记错误但实际错误的比特数 ÷ 总传输量 |
| **丢失率** | 被标记为错误（无效帧）的比特数 ÷ 总传输量 |
| **帧成功率** | 成功解析的帧数 ÷ 总帧数 |

**输出示例**：
```
============================================================
视频传输性能测试
============================================================

[视频信息]
  视频时长: 2814.79 ms
  指定测试时长: 1000 ms

[*] 正在分析视频帧...

[帧统计]
  提取帧数: 149
  去重跳过: 20
  有效帧: 117
  无效帧: 32 (CRC失败: 32, 解码失败: 0)
  去重后有效帧: 15 (帧ID: [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14])

[*] 正在逐帧对比...

============================================================
测试结果
============================================================

[传输量统计]
  有效传输量: 130,080 bits (16,260.0 bytes)
  总传输量:   1,299,280 bits (162,410.0 bytes)
  检查比特数: 130,080 bits
  实际错误比特: 0 bits
  标记错误比特: 279,040 bits

[性能指标]
  有效传输率: 130,080.00 bps (130.08 Kbps)
  误码率(BER): 0.0000%
  丢失率: 21.48%
  帧成功率: 78.52%
```

---

## 📊 帧结构设计

### 帧格式（8728 bits = 1091 bytes）

| 字段 | 长度 | 说明 |
|------|------|------|
| HEADER | 8 bits | 同步头 "10101010" |
| FRAME_ID | 16 bits | 帧序号 0-65535，用于排序 |
| DATA_LEN | 16 bits | 实际数据字节数 0-1084 |
| PAYLOAD | 8672 bits | 实际数据（1084 字节 × 8） |
| CRC | 16 bits | 校验和，覆盖 ID + LEN + PAYLOAD |

### 二维码矩阵（1920×1080）

- **矩阵大小**：128 × 72 格
- **单格像素**：15 × 15 像素
- **定位点**：11×11 回字形（四个角）
- **白边**：无（二维码占满整个画面）

---

## ⚙️ 配置参数

可在各脚本中修改以下参数：

| 参数 | 位置 | 默认值 | 说明 |
|------|------|--------|------|
| `VIDEO_WIDTH` | frame_design.py | 1920 | 视频宽度 |
| `VIDEO_HEIGHT` | frame_design.py | 1080 | 视频高度 |
| `CELL_SIZE` | frame_design.py | 15 | 单格像素大小 |
| `FINDER_SIZE` | frame_design.py | 11 | 定位点大小 |
| `PAYLOAD_LEN` | frame_design.py | 8672 | 每帧数据载荷位数 |
| `fps` | cli.py | 15 | 视频帧率 |
| `frame_repeat` | cli.py | 1 | 每帧重复次数 |

---

## 🔄 完整工作流

```bash
# 1. 准备输入文件
# 确保 input.bin 存在于项目目录

# 2. 编码成视频（1000ms）
python cli.py encode input.bin transmitter_video.mp4 1000

# 3. 用手机拍摄视频，替换 transmitter_video.mp4

# 4. 解码视频
python cli.py decode transmitter_video.mp4 out.bin vout.bin 1000

# 5. 性能测试
python test_performance.py input.bin out.bin transmitter_video.mp4 1000
```

---

## 🐛 常见问题

### Q: 解码准确率低？
**A**: 可能原因：
- 视频拍摄质量不佳（模糊、反光、遮挡）
- 透视变换精度不足（确保四个定位点都在画面内）
- 帧率设置过高，手机快门无法同步

**建议**：
- 使用 15 FPS，每帧播放 1 次
- 确保拍摄环境光线充足
- 手机与屏幕保持平行，减少透视变形

### Q: 如何优化传输速率？
**A**: 
- 降低帧率（15 FPS 比 30 FPS 更稳定）
- 减少每帧重复次数（1 次比 2 次效率更高）
- 确保视频质量，减少 CRC 失败帧

### Q: vout.bin 是什么？
**A**: 逐字节对比结果文件：
- `0xff` (255) - 该字节所有位都正确
- 其他值 - 表示错误的位（按位取反的异或结果）

### Q: 如何测试不同帧率？
**A**: 修改 `cli.py` 中的参数：
```python
fps = 15          # 帧率
frame_repeat = 1  # 每帧重复次数
```

---

## 📚 技术栈

- **Python 3.9+**: 脚本语言
- **OpenCV (cv2)**: 图像处理与视频编解码
- **NumPy**: 数值计算与矩阵操作
- **CRC-16**: 帧数据校验
- **透视变换**: 4点定位纠正

---

## 📄 许可证

MIT License

---

## 📝 更新日志

### 2026年3月25日
- 优化帧率为 15 FPS，每帧播放 1 次
- 实现 99.9992% 准确率（130080 位中仅 1 位错误）
- 有效传输率达到 130.08 Kbps
- 添加命令行接口（CLI）
- 添加性能测试工具

### 2026年3月19日
- 初始版本实现
- 1920×1080 分辨率，11×11 定位点
- 无白边设计
- 基础编解码功能

---

*Visible Light Communication Project*

**最后修改**: 2026 年 3 月 25 日
