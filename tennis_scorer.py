#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
网球自动计分系统 - 主程序

功能：
1. 自动检测得分圆圈位置（Gemini + 固定半径）
2. 检测击中事件（帧差法 + 颜色检测）
3. 自动计分并输出结果

使用方法：
    python tennis_scorer.py <视频路径>
    python tennis_scorer.py  # 使用默认视频
"""
import cv2
import numpy as np
import json
import sys
import os
import argparse
from datetime import datetime

# 导入核心模块
from detect_circles_final import detect_circles, extract_first_frame
from detect_hit_score import detect_and_score

# 默认配置
DEFAULT_VIDEO = "/Users/tgg_ai_studio/Desktop/tennis_score/hit.mov"
OUTPUT_DIR = "/Users/tgg_ai_studio/Desktop/tennis_score/output"


def print_banner():
    """打印横幅"""
    print()
    print("╔════════════════════════════════════════════════════════════╗")
    print("║           🎾 网球自动计分系统 Tennis Scorer 🎾              ║")
    print("╠════════════════════════════════════════════════════════════╣")
    print("║  功能：自动检测击中事件并计分                                ║")
    print("║  算法：Gemini圆圈检测 + 帧差法运动检测 + HSV颜色检测         ║")
    print("╚════════════════════════════════════════════════════════════╝")
    print()


def print_result(total_score, events):
    """打印结果"""
    print()
    print("╔════════════════════════════════════════════════════════════╗")
    print("║                        计分结果                             ║")
    print("╠════════════════════════════════════════════════════════════╣")

    for i, e in enumerate(events):
        time_str = f"{e['time']:.2f}s"
        if e['scored']:
            status = f"+{e['score']}分"
            line = f"║  事件{i+1}: {time_str:>8} → {status:>8}                          ║"
        else:
            line = f"║  事件{i+1}: {time_str:>8} → {'MISS':>8}                          ║"
        print(line)

    print("╠════════════════════════════════════════════════════════════╣")
    print(f"║                    总得分: {total_score:>3} 分                          ║")
    print("╚════════════════════════════════════════════════════════════╝")
    print()


def run_scoring(video_path, output_dir=None, force_detect_circles=False):
    """
    运行完整的计分流程

    Args:
        video_path: 视频路径
        output_dir: 输出目录
        force_detect_circles: 是否强制重新检测圆圈

    Returns:
        total_score: 总得分
        events: 击中事件列表
    """
    if output_dir is None:
        output_dir = OUTPUT_DIR

    os.makedirs(output_dir, exist_ok=True)

    circles_config_path = os.path.join(output_dir, "circles_config.json")
    first_frame_path = os.path.join(output_dir, "first_frame.jpg")

    print_banner()

    # Step 1: 检测圆圈（如果需要）
    if force_detect_circles or not os.path.exists(circles_config_path):
        print("[阶段1] 检测得分圆圈...")
        print("-" * 60)

        # 提取第一帧
        extract_first_frame(video_path, first_frame_path)

        # 检测圆圈
        circles = detect_circles(first_frame_path, output_dir)
        print()
    else:
        print("[阶段1] 使用已有的圆圈配置")
        print(f"    配置文件: {circles_config_path}")
        with open(circles_config_path, 'r') as f:
            circles = json.load(f)
        for c in circles:
            print(f"    {c['score']}分: 中心{c['center']}, 半径{c['radius']}")
        print()

    # Step 2: 检测击中并计分
    print("[阶段2] 检测击中事件并计分...")
    print("-" * 60)

    total_score, events = detect_and_score(
        video_path,
        circles_config_path=circles_config_path,
        output_dir=output_dir
    )

    # 打印结果
    print_result(total_score, events)

    # 保存结果
    result = {
        'video': video_path,
        'timestamp': datetime.now().isoformat(),
        'total_score': total_score,
        'events': events,
        'circles_config': circles
    }

    result_path = os.path.join(output_dir, "scoring_result.json")
    with open(result_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(f"[完成] 结果已保存: {result_path}")

    return total_score, events


def main():
    parser = argparse.ArgumentParser(description="网球自动计分系统")
    parser.add_argument("video", nargs="?", default=DEFAULT_VIDEO,
                        help="视频文件路径")
    parser.add_argument("-o", "--output", default=OUTPUT_DIR,
                        help="输出目录")
    parser.add_argument("-f", "--force", action="store_true",
                        help="强制重新检测圆圈")

    args = parser.parse_args()

    if not os.path.exists(args.video):
        print(f"错误: 视频文件不存在: {args.video}")
        sys.exit(1)

    total_score, events = run_scoring(
        args.video,
        output_dir=args.output,
        force_detect_circles=args.force
    )


if __name__ == "__main__":
    main()
