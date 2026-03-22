import cv2
import numpy as np

# 目标大小，根据需要调整
# 674x674 可以完整保留白边和二维码内容
target_size = (674, 674)

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
        
        # 过滤掉太小的轮廓
        if area < 100:
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
                candidates.append([cx, cy])

    # 需要至少 4 个点（现在四个角都是定位符）
    if len(candidates) < 4:
        return None
    
    # 几何排序：确定左上、右上、左下、右下
    pts = np.array(candidates, dtype="float32")
    
    # 计算所有点的中心（质心）
    center = np.mean(pts, axis=0)
    
    # 根据相对于中心的位置来排序
    # 左上: x < center_x, y < center_y
    # 右上: x > center_x, y < center_y
    # 左下: x < center_x, y > center_y
    # 右下: x > center_x, y > center_y
    
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
    # 假设二维码大致是正方形，计算平均边长
    all_dists = []
    for i in range(len(pts)):
        for j in range(i + 1, len(pts)):
            dist = np.sqrt(np.sum((pts[i] - pts[j])**2))
            all_dists.append(dist)
    all_dists.sort()
    # 取中间两个距离作为边长估计
    if len(all_dists) >= 4:
        avg_side = (all_dists[1] + all_dists[2]) / 2
    else:
        avg_side = np.mean(all_dists) if all_dists else 100
    
    # 期望的角点位置（相对于中心）
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
    
    # 返回 4 个点：左上、右上、左下、右下
    return np.float32([top_left, top_right, bottom_left, bottom_right])


def correct_frame(frame):
    """
    对帧进行透视变换，纠正二维码的角度和位置
    使用 4 点透视变换（参考 Visual-Net 的思想）
    """
    global last_frame_hash
    
    # 视觉去重逻辑
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    resized = cv2.resize(gray, (32, 32))
    curr_hash = resized.mean()
    
    if last_frame_hash is not None:
        # 原片极其稳定，阈值设为 0.1 即可过滤掉完全重复的帧
        if abs(curr_hash - last_frame_hash) < 0.1:
            return "SKIP"
    last_frame_hash = curr_hash

    # 执行定位
    src_points = find_anchor_centers(frame)
    if src_points is None:
        return None
    
    try:
        # 扩展源点以包含白边
        # 二维码结构：41x41 数据区 + 2x2 白边 = 45x45 总格子
        # 比例：45/41 ≈ 1.0975，需要向外扩展约 4.9%
        # 为了保险起见，使用 45/41 的比例
        
        top_left, top_right, bottom_left, bottom_right = src_points
        
        # 计算中心点
        center_x = (top_left[0] + top_right[0] + bottom_left[0] + bottom_right[0]) / 4
        center_y = (top_left[1] + top_right[1] + bottom_left[1] + bottom_right[1]) / 4
        center = np.array([center_x, center_y])
        
        # 扩展比例：调整到 1.30，避免黑边同时保留白边
        scale = 1.30
        
        # 从中心向外扩展
        src_points_expanded = np.float32([
            center + (top_left - center) * scale,      # 左上
            center + (top_right - center) * scale,     # 右上
            center + (bottom_left - center) * scale,   # 左下
            center + (bottom_right - center) * scale   # 右下
        ])
        
        # 目标点：4 个角点覆盖整个图片
        # 左上、右上、左下、右下
        dst_points = np.float32([
            [0, 0],                                # 左上
            [target_size[0] - 1, 0],               # 右上
            [0, target_size[1] - 1],               # 左下
            [target_size[0] - 1, target_size[1] - 1]  # 右下
        ])
        
        # 使用透视变换（4个点）
        M = cv2.getPerspectiveTransform(src_points_expanded, dst_points)
        # 使用最近邻插值，保持像素边缘清晰
        return cv2.warpPerspective(frame, M, target_size, flags=cv2.INTER_NEAREST)
    except Exception as e:
        print(f"透视变换失败: {e}")
        return None
