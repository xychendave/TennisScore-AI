# -*- coding: utf-8 -*-
"""
得分圆圈检测 - 最终方案
两阶段检测：Gemini 粗定位 + 固定半径

使用方法：
    python detect_circles_final.py <图片路径>
    python detect_circles_final.py  # 使用默认视频第一帧
"""
import base64
import json
import cv2
import re
import sys
import os
from google import genai
from google.genai import types

# 配置
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("请设置环境变量 GEMINI_API_KEY，获取地址: https://aistudio.google.com/apikey")
OUTPUT_DIR = "/Users/tgg_ai_studio/Desktop/tennis_score/output"

# 半径配置（原图坐标系，1920x1080）
RADIUS_CONFIG = {
    10: 27,  # 10分圆圈最大
    20: 20,  # 20分圆圈居中
    30: 15,  # 30分圆圈最小
}


def preprocess_image(image_path):
    """
    预处理：裁剪幕布区域 + 放大
    返回: (处理后的图片, 裁剪信息)
    """
    img = cv2.imread(image_path)
    h, w = img.shape[:2]

    # 根据图片尺寸动态计算幕布区域
    # 幕布大概在画面中上部，占画面的 30%-70% 宽度，15%-50% 高度
    x1 = int(w * 0.29)
    y1 = int(h * 0.26)
    x2 = int(w * 0.68)
    y2 = int(h * 0.46)

    curtain = img[y1:y2, x1:x2]

    # 放大 2 倍提高识别精度
    scale = 2
    enlarged = cv2.resize(curtain, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)

    crop_info = {
        'crop': {'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2},
        'scale': scale,
        'original_size': [w, h]
    }

    return enlarged, crop_info


def detect_with_gemini(image):
    """
    阶段1：使用 Gemini 检测圆圈位置
    返回: 圆圈列表 [{'score': 10, 'center': [x, y]}, ...]
    """
    # 编码图片
    _, buffer = cv2.imencode('.jpg', image, [cv2.IMWRITE_JPEG_QUALITY, 90])
    image_data = base64.standard_b64encode(buffer).decode('utf-8')

    h, w = image.shape[:2]

    # 调用 Gemini
    client = genai.Client(api_key=GEMINI_API_KEY)

    prompt = """帮我标出图上 10 分 30 分 20 分的6个得分圆圈

返回JSON格式:
[{"box_2d": [y1, x1, y2, x2], "label": "10"}, ...]
坐标使用0-1000归一化值"""

    contents = [
        types.Content(
            role="user",
            parts=[
                types.Part.from_bytes(
                    data=base64.standard_b64decode(image_data),
                    mime_type="image/jpeg"
                ),
                types.Part.from_text(text=prompt),
            ],
        ),
    ]

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=contents,
        config=types.GenerateContentConfig(temperature=0.1),
    )

    # 解析响应
    json_match = re.search(r'\[[\s\S]*\]', response.text)
    if not json_match:
        raise ValueError(f"无法解析 Gemini 响应: {response.text[:200]}")

    boxes = json.loads(json_match.group())

    # 转换坐标
    scale_x = w / 1000
    scale_y = h / 1000

    circles = []
    for box in boxes:
        y1, x1, y2, x2 = box['box_2d']
        label = str(box.get('label', '10'))

        # 计算中心点（像素坐标）
        cx = int((x1 + x2) / 2 * scale_x)
        cy = int((y1 + y2) / 2 * scale_y)

        # 提取分数
        score_match = re.search(r'\d+', label)
        score = int(score_match.group()) if score_match else 10

        circles.append({
            'score': score,
            'center': [cx, cy]
        })

    return circles


def convert_to_original_coords(circles, crop_info):
    """
    将裁剪图坐标转换回原图坐标，并添加固定半径
    """
    crop = crop_info['crop']
    scale = crop_info['scale']

    result = []
    for c in circles:
        cx, cy = c['center']
        score = c['score']

        # 转换坐标
        orig_cx = int(cx / scale + crop['x1'])
        orig_cy = int(cy / scale + crop['y1'])

        # 使用固定半径
        radius = RADIUS_CONFIG.get(score, 20)

        result.append({
            'score': score,
            'center': [orig_cx, orig_cy],
            'radius': radius
        })

    return result


def draw_results(image_path, circles, output_path):
    """绘制检测结果"""
    img = cv2.imread(image_path)

    colors = {
        10: (0, 255, 0),    # 绿色
        20: (0, 255, 255),  # 黄色
        30: (0, 165, 255),  # 橙色
    }

    for c in circles:
        cx, cy = c['center']
        radius = c['radius']
        score = c['score']
        color = colors.get(score, (255, 255, 255))

        cv2.circle(img, (cx, cy), radius, color, 2)
        cv2.circle(img, (cx, cy), 4, color, -1)
        cv2.putText(img, f"{score}pts r={radius}",
                    (cx - 40, cy - radius - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

    cv2.imwrite(output_path, img)
    return output_path


def detect_circles(image_path, output_dir=None):
    """
    主函数：检测得分圆圈

    Args:
        image_path: 输入图片路径
        output_dir: 输出目录，默认为 OUTPUT_DIR

    Returns:
        circles: 检测到的圆圈列表
    """
    if output_dir is None:
        output_dir = OUTPUT_DIR

    os.makedirs(output_dir, exist_ok=True)

    print("=" * 50)
    print("得分圆圈检测 - Gemini 粗定位 + 固定半径")
    print("=" * 50)

    # Step 1: 预处理
    print("\n[1] 预处理图片...")
    preprocessed, crop_info = preprocess_image(image_path)
    print(f"    裁剪区域: {crop_info['crop']}")
    print(f"    放大倍数: {crop_info['scale']}x")

    # 保存预处理图片（调试用）
    preprocessed_path = os.path.join(output_dir, "preprocessed.jpg")
    cv2.imwrite(preprocessed_path, preprocessed)

    # Step 2: Gemini 检测
    print("\n[2] Gemini 粗定位...")
    circles_local = detect_with_gemini(preprocessed)
    print(f"    检测到 {len(circles_local)} 个圆圈")

    # Step 3: 坐标转换 + 固定半径
    print("\n[3] 坐标转换 + 添加半径...")
    circles = convert_to_original_coords(circles_local, crop_info)

    for c in circles:
        print(f"    {c['score']}分: 中心({c['center'][0]:4d}, {c['center'][1]:4d}), 半径 {c['radius']}px")

    # Step 4: 保存结果
    print("\n[4] 保存结果...")

    # 可视化
    output_img_path = os.path.join(output_dir, "detected_circles_final.jpg")
    draw_results(image_path, circles, output_img_path)
    print(f"    结果图: {output_img_path}")

    # 配置文件
    config_path = os.path.join(output_dir, "circles_config.json")
    with open(config_path, 'w') as f:
        json.dump(circles, f, indent=2)
    print(f"    配置文件: {config_path}")

    print("\n" + "=" * 50)
    print("检测完成!")
    print("=" * 50)

    return circles


def extract_first_frame(video_path, output_path):
    """从视频提取第一帧"""
    cap = cv2.VideoCapture(video_path)
    ret, frame = cap.read()
    cap.release()

    if ret:
        cv2.imwrite(output_path, frame)
        return output_path
    return None


if __name__ == "__main__":
    # 默认使用视频第一帧
    if len(sys.argv) > 1:
        image_path = sys.argv[1]
    else:
        # 从视频提取第一帧
        video_path = "/Users/tgg_ai_studio/Desktop/tennis_score/hit.mov"
        image_path = "/Users/tgg_ai_studio/Desktop/tennis_score/hit_first_frame.jpg"

        if not os.path.exists(image_path):
            print(f"从视频提取第一帧: {video_path}")
            extract_first_frame(video_path, image_path)

    # 检测圆圈
    circles = detect_circles(image_path)
