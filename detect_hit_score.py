#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
网球击中检测与计分算法

算法逻辑：
1. 帧差法检测幕布区域的运动量
2. 找到运动量超过阈值的帧 = 击中瞬间
3. 在击中帧用颜色检测找球位置
4. 判断球是否在得分圈内
5. 冷却时间防止重复计分

使用方法：
    python detect_hit_score.py <视频路径>
    python detect_hit_score.py  # 使用默认视频
"""
import cv2
import numpy as np
import json
import sys
import os

# 默认配置
DEFAULT_VIDEO = "/Users/tgg_ai_studio/Desktop/tennis_score/hit.mov"
OUTPUT_DIR = "/Users/tgg_ai_studio/Desktop/tennis_score/output"
CIRCLES_CONFIG = "/Users/tgg_ai_studio/Desktop/tennis_score/output/circles_config.json"

# 检测参数
COOLDOWN_SEC = 1.5  # 冷却时间（秒）- 防止同一次击中被多次计分
MOTION_THRESHOLD_FACTOR = 1.5  # 运动阈值 = 平均 + N倍标准差（降低以检测更多击中）
HIT_TOLERANCE = 15  # 击中判定容差（像素）

# 球颜色范围 (HSV)
BALL_COLOR_LOWER = np.array([20, 80, 80])
BALL_COLOR_UPPER = np.array([45, 255, 255])


def get_curtain_roi(circles_config, margin=20):
    """
    根据圆圈配置计算幕布区域
    只包含圆圈区域，不要太大以免检测到其他运动
    """
    all_x = [c['center'][0] for c in circles_config]
    all_y = [c['center'][1] for c in circles_config]
    max_r = max(c['radius'] for c in circles_config)

    # 紧凑的区域，只覆盖圆圈
    x1 = min(all_x) - max_r - margin
    y1 = min(all_y) - max_r - margin
    x2 = max(all_x) + max_r + margin
    y2 = max(all_y) + max_r + margin

    return (int(x1), int(y1), int(x2), int(y2))


def detect_motion(video_path, curtain_roi):
    """
    检测视频中幕布区域的运动
    返回：每帧的运动量和帧数据
    """
    cx1, cy1, cx2, cy2 = curtain_roi

    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    prev_curtain = None
    frames_data = []

    frame_idx = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break

        # 提取幕布区域
        curtain = frame[cy1:cy2, cx1:cx2]
        gray = cv2.cvtColor(curtain, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (5, 5), 0)

        # 计算帧差
        if prev_curtain is not None:
            diff = cv2.absdiff(prev_curtain, gray)
            motion_score = np.sum(diff)
        else:
            motion_score = 0

        frames_data.append({
            'idx': frame_idx,
            'time': frame_idx / fps,
            'motion': motion_score,
            'frame': frame.copy()
        })

        prev_curtain = gray
        frame_idx += 1

    cap.release()
    return frames_data, fps


def find_hit_events(frames_data, fps, threshold_factor=1.5, cooldown_sec=1.0):
    """
    找到击中事件（运动量超过阈值的帧）
    在冷却期内找运动量最大的那一帧（击中瞬间）
    """
    motion_scores = [f['motion'] for f in frames_data]
    avg_motion = np.mean(motion_scores)
    std_motion = np.std(motion_scores)
    threshold = avg_motion + threshold_factor * std_motion

    cooldown_frames = int(fps * cooldown_sec)
    hit_events = []

    # 跳过开头的几帧（避免摄像机初始化误检）
    start_frame = int(fps * 0.5)  # 从0.5秒开始检测

    i = start_frame
    while i < len(frames_data):
        fd = frames_data[i]
        if fd['motion'] > threshold:
            # 找到一个超过阈值的帧，在接下来的一段时间内找最大值
            peak_frame = fd
            j = i + 1
            while j < len(frames_data) and j - i < cooldown_frames:
                if frames_data[j]['motion'] > peak_frame['motion']:
                    peak_frame = frames_data[j]
                j += 1

            hit_events.append(peak_frame)
            # 跳过冷却期
            i = i + cooldown_frames
        else:
            i += 1

    return hit_events, threshold


def detect_ball_in_frame(frame, curtain_roi):
    """
    在帧中检测球的位置
    返回：球的坐标 (x, y) 或 None
    """
    cx1, cy1, cx2, cy2 = curtain_roi
    curtain = frame[cy1:cy2, cx1:cx2]

    # HSV 颜色检测
    hsv = cv2.cvtColor(curtain, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, BALL_COLOR_LOWER, BALL_COLOR_UPPER)
    mask = cv2.dilate(mask, None, iterations=2)

    # 找轮廓
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    for c in contours:
        area = cv2.contourArea(c)
        if 30 < area < 2000:  # 球的大小范围
            M = cv2.moments(c)
            if M['m00'] > 0:
                bx = int(M['m10'] / M['m00']) + cx1
                by = int(M['m01'] / M['m00']) + cy1
                return (bx, by)

    return None


def check_score(ball_pos, circles_config, tolerance=15):
    """
    判断球是否在得分圈内
    返回：(是否得分, 分数, 命中的圆圈)
    """
    if ball_pos is None:
        return False, 0, None

    for c in circles_config:
        cx, cy = c['center']
        radius = c['radius']
        dist = np.sqrt((ball_pos[0] - cx)**2 + (ball_pos[1] - cy)**2)

        if dist <= radius + tolerance:
            return True, c['score'], c

    return False, 0, None


def draw_result(frame, curtain_roi, circles_config, ball_pos, scored, score, time_sec):
    """绘制检测结果"""
    result = frame.copy()
    cx1, cy1, cx2, cy2 = curtain_roi

    # 画幕布区域
    cv2.rectangle(result, (cx1, cy1), (cx2, cy2), (255, 255, 255), 1)

    # 画得分圈
    colors = {10: (0, 255, 0), 20: (0, 255, 255), 30: (0, 165, 255)}
    for c in circles_config:
        cv2.circle(result, tuple(c['center']), c['radius'], colors.get(c['score'], (255, 255, 255)), 2)

    # 画球和标注
    if ball_pos:
        color = (0, 255, 0) if scored else (0, 0, 255)
        cv2.circle(result, ball_pos, 15, color, 3)
        status = f"+{score}" if scored else "MISS"
        cv2.putText(result, f"{time_sec:.2f}s {status}",
                    (ball_pos[0] - 50, ball_pos[1] - 25),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)

    return result


def detect_and_score(video_path, circles_config_path=None, output_dir=None):
    """
    主函数：检测击中并计分

    Args:
        video_path: 视频路径
        circles_config_path: 圆圈配置文件路径
        output_dir: 输出目录

    Returns:
        total_score: 总得分
        events: 击中事件列表
    """
    if circles_config_path is None:
        circles_config_path = CIRCLES_CONFIG
    if output_dir is None:
        output_dir = OUTPUT_DIR

    os.makedirs(output_dir, exist_ok=True)

    # 读取圆圈配置
    with open(circles_config_path, 'r') as f:
        circles_config = json.load(f)

    # 计算幕布区域
    curtain_roi = get_curtain_roi(circles_config)

    print("=" * 60)
    print("网球击中检测与计分")
    print("=" * 60)
    print(f"视频: {video_path}")
    print(f"幕布区域: {curtain_roi}")
    print(f"冷却时间: {COOLDOWN_SEC}秒")

    # Step 1: 检测运动
    print("\n[1] 检测幕布运动...")
    frames_data, fps = detect_motion(video_path, curtain_roi)
    print(f"    视频: {fps:.1f} fps, {len(frames_data)} 帧")

    # Step 2: 找击中事件
    print("\n[2] 识别击中事件...")
    hit_events, threshold = find_hit_events(
        frames_data, fps,
        threshold_factor=MOTION_THRESHOLD_FACTOR,
        cooldown_sec=COOLDOWN_SEC
    )
    print(f"    运动阈值: {threshold:.0f}")
    print(f"    检测到 {len(hit_events)} 次击中")

    # Step 3: 检测球位置并计分
    print("\n[3] 计分判定...")
    print("-" * 50)

    total_score = 0
    events = []

    for i, event in enumerate(hit_events):
        ball_pos = detect_ball_in_frame(event['frame'], curtain_roi)
        scored, score, hit_circle = check_score(ball_pos, circles_config, HIT_TOLERANCE)

        if scored:
            total_score += score
            status = f"+{score}分"
        else:
            status = "MISS"

        ball_str = f"{ball_pos}" if ball_pos else "未检测到"
        print(f"  事件{i+1}: {event['time']:.2f}s, 球={ball_str} → {status}")

        # 保存结果
        events.append({
            'time': event['time'],
            'ball_pos': ball_pos,
            'scored': scored,
            'score': score
        })

        # 保存图片
        result_img = draw_result(
            event['frame'], curtain_roi, circles_config,
            ball_pos, scored, score, event['time']
        )
        cv2.imwrite(f"{output_dir}/hit_event_{i+1}.jpg", result_img)

    print("-" * 50)
    print(f"\n[结果] 总得分: {total_score} 分")
    print("=" * 60)

    return total_score, events


if __name__ == "__main__":
    video_path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_VIDEO
    total_score, events = detect_and_score(video_path)
