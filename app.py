#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
网球计分系统 - Web 应用
"""
import os
import json
import uuid
from flask import Flask, render_template, request, jsonify, send_from_directory
from werkzeug.utils import secure_filename

# 导入计分模块
from detect_circles_final import detect_circles, extract_first_frame
from detect_hit_score import detect_and_score

app = Flask(__name__, static_folder='static', template_folder='templates')

# 配置
UPLOAD_FOLDER = '/Users/tgg_ai_studio/Desktop/tennis_score/uploads'
OUTPUT_FOLDER = '/Users/tgg_ai_studio/Desktop/tennis_score/output'
ALLOWED_EXTENSIONS = {'mov', 'mp4', 'avi', 'mkv'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB max

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/')
def index():
    """主页"""
    return render_template('index.html')


@app.route('/api/upload', methods=['POST'])
def upload_video():
    """上传视频并处理"""
    if 'video' not in request.files:
        return jsonify({'error': '没有上传文件'}), 400

    file = request.files['video']
    if file.filename == '':
        return jsonify({'error': '没有选择文件'}), 400

    if not allowed_file(file.filename):
        return jsonify({'error': '不支持的文件格式'}), 400

    # 保存文件
    task_id = str(uuid.uuid4())[:8]
    filename = secure_filename(f"{task_id}_{file.filename}")
    video_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(video_path)

    # 创建任务输出目录
    task_output_dir = os.path.join(OUTPUT_FOLDER, task_id)
    os.makedirs(task_output_dir, exist_ok=True)

    try:
        # Step 1: 提取第一帧
        first_frame_path = os.path.join(task_output_dir, "first_frame.jpg")
        extract_first_frame(video_path, first_frame_path)

        # Step 2: 检测圆圈
        circles = detect_circles(first_frame_path, task_output_dir)

        # Step 3: 检测击中并计分
        circles_config_path = os.path.join(task_output_dir, "circles_config.json")
        total_score, events = detect_and_score(
            video_path,
            circles_config_path=circles_config_path,
            output_dir=task_output_dir
        )

        # 构建结果
        result = {
            'task_id': task_id,
            'total_score': total_score,
            'events': events,
            'circles': circles,
            'images': {
                'first_frame': f'/output/{task_id}/first_frame.jpg',
                'circles': f'/output/{task_id}/detected_circles_final.jpg',
            }
        }

        # 添加击中事件图片
        hit_images = []
        for i in range(len(events)):
            img_path = f'/output/{task_id}/hit_event_{i+1}.jpg'
            hit_images.append(img_path)
        result['images']['hits'] = hit_images

        return jsonify(result)

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/demo')
def demo():
    """使用默认视频进行演示"""
    demo_video = '/Users/tgg_ai_studio/Desktop/tennis_score/hit.mov'
    task_id = 'demo'
    task_output_dir = os.path.join(OUTPUT_FOLDER, task_id)
    os.makedirs(task_output_dir, exist_ok=True)

    try:
        # 提取第一帧
        first_frame_path = os.path.join(task_output_dir, "first_frame.jpg")
        extract_first_frame(demo_video, first_frame_path)

        # 检测圆圈
        circles = detect_circles(first_frame_path, task_output_dir)

        # 检测击中并计分
        circles_config_path = os.path.join(task_output_dir, "circles_config.json")
        total_score, events = detect_and_score(
            demo_video,
            circles_config_path=circles_config_path,
            output_dir=task_output_dir
        )

        result = {
            'task_id': task_id,
            'total_score': total_score,
            'events': events,
            'circles': circles,
            'images': {
                'first_frame': f'/output/{task_id}/first_frame.jpg',
                'circles': f'/output/{task_id}/detected_circles_final.jpg',
                'hits': [f'/output/{task_id}/hit_event_{i+1}.jpg' for i in range(len(events))]
            }
        }

        return jsonify(result)

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/output/<path:filename>')
def serve_output(filename):
    """提供输出文件"""
    return send_from_directory(OUTPUT_FOLDER, filename)


if __name__ == '__main__':
    print("\n" + "=" * 60)
    print("🎾 网球计分系统 Web 应用")
    print("=" * 60)
    print("访问地址: http://localhost:5001")
    print("=" * 60 + "\n")
    app.run(host='0.0.0.0', port=5001, debug=True)
