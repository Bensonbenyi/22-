import cv2
import numpy as np
from frame_design import QR_WIDTH, QR_HEIGHT, FINDER_SIZE

# 视频和矩阵配置
VIDEO_WIDTH = 1920
VIDEO_HEIGHT = 1080
CELL_SIZE = 15  # 每个矩阵格子的像素大小
BORDER_CELLS = 0  # 无白边

# 透视变换输出大小（无白边，直接就是 1920x1080）
# 二维码实际大小：128x72 格子，每格15像素 = 1920x1080
target_size = (VIDEO_WIDTH, VIDEO_HEIGHT)  # (1920, 1080)

# 计算定位点在输出图像中的位置
# 【无白边】目标点应该让定位点外边缘对齐图像边缘，而不是中心

# 定位点从 (0,0) 开始，大小 11x11 = 165x165 像素
# 定位点中心在 (5,5) 格 = (75,75) 像素
# 为了让整个二维码占满 1920x1080，定位点的外边缘应该对齐图像边缘

# 左上定位点：外边缘从 (0,0) 开始，中心在 (75,75)
# 如果中心映射到 (75,75)，那么外边缘 (0,0) 会被映射到 (0,0) ✓
# 但这样定位点只占 (0,0) 到 (150,150)，不是从 (0,0) 到 (165,165)

# 正确的计算：
# 检测到的定位点中心 -> 映射到定位点中心应该的位置
# 左上定位点中心应该在 (75, 75)
# 右上定位点中心应该在 (1920-75, 75) = (1845, 75)
# 左下定位点中心应该在 (75, 1080-75) = (75, 1005)
# 右下定位点中心应该在 (1920-75, 1080-75) = (1845, 1005)
FINDER_CENTER_OFFSET = (FINDER_SIZE - 1) / 2 * CELL_SIZE  # 75

# 目标点：定位点中心在输出图像中的位置
# 由于透视变换会放大图像，导致边缘格子只有一半
# 所以将目标点向内收缩 7.5 像素（半个格子），让边缘完整显示
SHRINK_PX = 7.5  # 半个格子
DST_TOP_LEFT = (FINDER_CENTER_OFFSET + SHRINK_PX, FINDER_CENTER_OFFSET + SHRINK_PX)  # (82.5, 82.5)
DST_TOP_RIGHT = (VIDEO_WIDTH - FINDER_CENTER_OFFSET - SHRINK_PX, FINDER_CENTER_OFFSET + SHRINK_PX)  # (1837.5, 82.5)
DST_BOTTOM_LEFT = (FINDER_CENTER_OFFSET + SHRINK_PX, VIDEO_HEIGHT - FINDER_CENTER_OFFSET - SHRINK_PX)  # (82.5, 997.5)
DST_BOTTOM_RIGHT = (VIDEO_WIDTH - FINDER_CENTER_OFFSET - SHRINK_PX, VIDEO_HEIGHT - FINDER_CENTER_OFFSET - SHRINK_PX)  # (1837.5, 997.5)

# 上一帧的哈希值，用于去重
last_frame_hash = None


def reset_frame_hash():
    """重置帧哈希缓存，在每次新视频处理前调用"""
    global last_frame_hash
    last_frame_hash = None


def find_anchor_centers(img):
    """
    寻找二维码的四个定位点中心
    使用改进的二值化方法应对反光问题
    适配 1920x1080 分辨率和更大的二维码（11x11定位点）
    【无白边版本】
    """
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # 预处理：使用高斯模糊减少噪声
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    
    # 方法1: OTSU自动阈值（适用于反光不均匀的情况）
    _, binary_otsu = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    
    # 方法2: 自适应阈值（适用于光照变化）
    binary_adaptive = cv2.adaptiveThreshold(blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                           cv2.THRESH_BINARY_INV, 21, 5)
    
    # 合并两种方法的结果（取交集，更严格）
    binary = cv2.bitwise_and(binary_otsu, binary_adaptive)
    
    # 形态学操作：先腐蚀去除小噪点，再膨胀连接断裂部分
    kernel = np.ones((3, 3), np.uint8)
    binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel, iterations=1)
    binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel, iterations=1)
    
    # 使用 RETR_TREE 获取完整的轮廓嵌套层级 (Hierarchy)
    contours, hierarchy = cv2.findContours(binary, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    
    if hierarchy is None:
        return None
    
    hier = hierarchy[0]
    candidates = []
    
    for i, cnt in enumerate(contours):
        area = cv2.contourArea(cnt)
        
        # 调整面积范围：11x11 定位符在 1920x1080 画面中更大
        if area < 1000 or area > 50000:
            continue
        
        # --- 过滤逻辑 1：外接矩形比例 ---
        x, y, w, h = cv2.boundingRect(cnt)
        aspect_ratio = float(w) / h
        if not (0.8 < aspect_ratio < 1.2):
            continue
        
        # --- 过滤逻辑 2：层级结构 ---
        # 定位符有内部黑框，因此必有子轮廓
        # 寻找嵌套层级 >= 2 的轮廓（回字形结构）
        k, depth = i, 0
        while hier[k][2] != -1:
            k = hier[k][2]
            depth += 1
        
        if depth >= 2:
            M = cv2.moments(cnt)
            if M["m00"] != 0:
                cx = int(M["m10"] / M["m00"])
                cy = int(M["m01"] / M["m00"])
                candidates.append([cx, cy, area])  # 同时记录面积
    
    # 如果候选点超过4个，选择面积最接近的4个（11x11定位符面积应该相近）
    if len(candidates) > 4:
        # 计算平均面积
        avg_area = np.mean([c[2] for c in candidates])
        # 按与平均面积的差距排序
        candidates.sort(key=lambda x: abs(x[2] - avg_area))
        candidates = candidates[:4]
    
    # 去掉面积信息，只保留坐标
    candidates = [[c[0], c[1]] for c in candidates]

    # 需要至少 4 个点（现在四个角都是定位符）
    if len(candidates) < 4:
        return None
    
    # 几何排序：确定左上、右上、左下、右下
    pts = np.array(candidates, dtype="float32")
    
    # 计算所有点的中心（质心）
    center = np.mean(pts, axis=0)
    
    # 根据相对于中心的位置来排序
    top_left_candidates = []
    top_right_candidates = []
    bottom_left_candidates = []
    bottom_right_candidates = []
    
    for pt in pts:
        if pt[0] < center[0] and pt[1] < center[1]:
            top_left_candidates.append(pt)
        elif pt[0] > center[0] and pt[1] < center[1]:
            top_right_candidates.append(pt)
        elif pt[0] < center[0] and pt[1] > center[1]:
            bottom_left_candidates.append(pt)
        elif pt[0] > center[0] and pt[1] > center[1]:
            bottom_right_candidates.append(pt)
    
    # 如果每个象限都有且只有一个点，直接返回
    if len(top_left_candidates) == 1 and len(top_right_candidates) == 1 and \
       len(bottom_left_candidates) == 1 and len(bottom_right_candidates) == 1:
        top_left = top_left_candidates[0]
        top_right = top_right_candidates[0]
        bottom_left = bottom_left_candidates[0]
        bottom_right = bottom_right_candidates[0]
        return np.float32([top_left, top_right, bottom_left, bottom_right])
    
    # 如果有多个点在同一象限，选择距离中心最近的
    def closest_to_center(candidates_list, center_point):
        if not candidates_list:
            return None
        distances = [np.sqrt(np.sum((pt - center_point)**2)) for pt in candidates_list]
        return candidates_list[np.argmin(distances)]
    
    # 计算期望的中心偏移（用于选择正确的点）
    all_dists = []
    for i in range(len(pts)):
        for j in range(i + 1, len(pts)):
            dist = np.sqrt(np.sum((pts[i] - pts[j])**2))
            all_dists.append(dist)
    all_dists.sort()
    if len(all_dists) >= 4:
        avg_side = (all_dists[1] + all_dists[2]) / 2
    else:
        avg_side = np.mean(all_dists) if all_dists else 100
    
    offset = avg_side / 2
    expected_tl = center + np.array([-offset, -offset])
    expected_tr = center + np.array([offset, -offset])
    expected_bl = center + np.array([-offset, offset])
    expected_br = center + np.array([offset, offset])
    
    top_left = closest_to_center(top_left_candidates if top_left_candidates else pts.tolist(), expected_tl)
    top_right = closest_to_center(top_right_candidates if top_right_candidates else pts.tolist(), expected_tr)
    bottom_left = closest_to_center(bottom_left_candidates if bottom_left_candidates else pts.tolist(), expected_bl)
    bottom_right = closest_to_center(bottom_right_candidates if bottom_right_candidates else pts.tolist(), expected_br)
    
    if top_left is None or top_right is None or bottom_left is None or bottom_right is None:
        return None
    
    return np.float32([top_left, top_right, bottom_left, bottom_right])


def correct_frame(frame):
    """
    对帧进行透视变换，纠正二维码的角度和位置
    使用 4 点透视变换，输出 1920x1080（无白边）
    """
    global last_frame_hash
    
    # 视觉去重逻辑
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    resized = cv2.resize(gray, (32, 32))
    curr_hash = resized.mean()
    
    if last_frame_hash is not None:
        if abs(curr_hash - last_frame_hash) < 0.1:
            return "SKIP"
    last_frame_hash = curr_hash

    # 执行定位
    src_points = find_anchor_centers(frame)
    if src_points is None:
        return None
    
    try:
        top_left, top_right, bottom_left, bottom_right = src_points
        
        # 源点：检测到的定位点中心
        src_points_direct = np.float32([
            top_left,      # 左上
            top_right,     # 右上
            bottom_left,   # 左下
            bottom_right   # 右下
        ])
        
        # 目标点：定位点中心在输出图像中的对应位置（无白边版本）
        dst_points = np.float32([
            DST_TOP_LEFT,      # 左上
            DST_TOP_RIGHT,     # 右上
            DST_BOTTOM_LEFT,   # 左下
            DST_BOTTOM_RIGHT   # 右下
        ])
        
        # 使用透视变换（4个点）
        M = cv2.getPerspectiveTransform(src_points_direct, dst_points)
        # 使用最近邻插值，保持像素边缘清晰
        return cv2.warpPerspective(frame, M, target_size, flags=cv2.INTER_NEAREST)
    except Exception as e:
        print(f"透视变换失败: {e}")
        return None
