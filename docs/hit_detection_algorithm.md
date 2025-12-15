# 击中检测与计分算法文档

## 1. 算法概述

本算法用于检测网球击中幕布的事件，并根据击中位置判断得分。

### 1.1 核心流程

```
┌─────────────────────────────────────────────────────────────┐
│                    击中检测与计分流程                         │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Step 1: 帧差法检测运动                                      │
│  ┌─────────────────────────────────────┐                    │
│  │  对幕布区域逐帧计算像素变化量          │                    │
│  │  motion_score = sum(|frame_n - frame_n-1|)              │
│  └─────────────────────────────────────┘                    │
│                       ↓                                     │
│  Step 2: 识别击中帧                                          │
│  ┌─────────────────────────────────────┐                    │
│  │  阈值 = 平均运动量 + 2×标准差         │                    │
│  │  运动量 > 阈值 → 击中事件             │                    │
│  │  冷却时间1秒内不重复计分              │                    │
│  └─────────────────────────────────────┘                    │
│                       ↓                                     │
│  Step 3: 检测球位置                                          │
│  ┌─────────────────────────────────────┐                    │
│  │  HSV颜色检测黄绿色网球               │                    │
│  │  找轮廓 → 计算质心坐标               │                    │
│  └─────────────────────────────────────┘                    │
│                       ↓                                     │
│  Step 4: 判断得分                                            │
│  ┌─────────────────────────────────────┐                    │
│  │  计算球位置到各圆圈中心的距离         │                    │
│  │  距离 <= 半径 + 容差 → 得分           │                    │
│  └─────────────────────────────────────┘                    │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. 关键参数

### 2.1 检测参数

```python
COOLDOWN_SEC = 1.0           # 冷却时间（秒）
MOTION_THRESHOLD_FACTOR = 2.0 # 阈值 = 平均 + N×标准差
HIT_TOLERANCE = 15           # 击中判定容差（像素）
```

### 2.2 球颜色范围 (HSV)

```python
BALL_COLOR_LOWER = [20, 80, 80]   # 黄绿色下限
BALL_COLOR_UPPER = [45, 255, 255] # 黄绿色上限
```

### 2.3 幕布区域

根据圆圈配置自动计算：
```python
x1 = min(圆心X) - 最大半径 - 边距
y1 = min(圆心Y) - 最大半径 - 边距
x2 = max(圆心X) + 最大半径 + 边距
y2 = max(圆心Y) + 最大半径 + 边距
```

---

## 3. 算法详解

### 3.1 帧差法检测运动

```python
def detect_motion(video_path, curtain_roi):
    prev_curtain = None

    for frame in video:
        # 提取幕布区域
        curtain = frame[y1:y2, x1:x2]
        gray = cv2.cvtColor(curtain, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (5, 5), 0)

        # 计算帧差
        if prev_curtain is not None:
            diff = cv2.absdiff(prev_curtain, gray)
            motion_score = np.sum(diff)  # 总变化量

        prev_curtain = gray
```

**关键点：**
- 只检测幕布区域，排除人员走动干扰
- 高斯模糊去噪
- 用像素差异总和作为运动量指标

### 3.2 击中事件识别

```python
def find_hit_events(frames_data, fps):
    # 动态阈值
    avg = np.mean(motion_scores)
    std = np.std(motion_scores)
    threshold = avg + 2 * std

    # 带冷却的事件检测
    cooldown_frames = int(fps * 1.0)
    last_hit = -cooldown_frames

    for frame in frames_data:
        if frame.motion > threshold:
            if frame.idx - last_hit >= cooldown_frames:
                hit_events.append(frame)
                last_hit = frame.idx
```

**关键点：**
- 动态阈值适应不同视频
- 冷却时间防止一次击中被多次计分

### 3.3 球位置检测

```python
def detect_ball_in_frame(frame, curtain_roi):
    # HSV 颜色检测
    hsv = cv2.cvtColor(curtain, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, BALL_COLOR_LOWER, BALL_COLOR_UPPER)

    # 形态学处理
    mask = cv2.dilate(mask, None, iterations=2)

    # 找轮廓计算质心
    contours = cv2.findContours(mask, ...)
    for c in contours:
        if 30 < area < 2000:  # 球的大小范围
            cx = M['m10'] / M['m00']
            cy = M['m01'] / M['m00']
            return (cx, cy)
```

**关键点：**
- 黄绿色网球在 HSV 空间更容易区分
- 面积过滤排除噪声

### 3.4 得分判定

```python
def check_score(ball_pos, circles_config, tolerance=15):
    for circle in circles_config:
        dist = sqrt((ball_x - circle_x)^2 + (ball_y - circle_y)^2)

        if dist <= radius + tolerance:
            return True, circle.score

    return False, 0
```

**关键点：**
- 15像素容差补偿检测误差
- 遍历所有圆圈找最近的

---

## 4. 使用方法

### 4.1 命令行

```bash
# 使用默认视频
python detect_hit_score.py

# 指定视频
python detect_hit_score.py /path/to/video.mov
```

### 4.2 代码调用

```python
from detect_hit_score import detect_and_score

total_score, events = detect_and_score(
    video_path="hit.mov",
    circles_config_path="output/circles_config.json"
)

print(f"总得分: {total_score}")
for e in events:
    print(f"{e['time']:.2f}s: {'+' + str(e['score']) if e['scored'] else 'MISS'}")
```

---

## 5. 输出文件

| 文件 | 说明 |
|-----|------|
| `output/hit_event_N.jpg` | 第N次击中的结果图 |
| `output/circles_config.json` | 得分圈配置（需预先生成） |

---

## 6. 调参指南

### 6.1 漏检（没检测到击中）

- 降低 `MOTION_THRESHOLD_FACTOR`（如 1.5）
- 检查幕布区域是否正确

### 6.2 误检（检测到不存在的击中）

- 提高 `MOTION_THRESHOLD_FACTOR`（如 2.5）
- 增加 `COOLDOWN_SEC`

### 6.3 球位置检测不到

- 调整 `BALL_COLOR_LOWER/UPPER` 范围
- 检查光照是否影响颜色

### 6.4 得分判定不准

- 增加 `HIT_TOLERANCE`
- 重新校准圆圈位置

---

## 7. 完整流程

```
1. 先运行圆圈检测: python detect_circles_final.py
2. 再运行计分检测: python detect_hit_score.py
```

---

## 8. 版本历史

| 日期 | 版本 | 修改内容 |
|-----|------|---------|
| 2024-12-15 | v1.0 | 初版：帧差法 + 颜色检测 + 冷却时间 |
