# 得分圆圈检测算法文档

## 1. 算法概述

本算法用于检测网球发球机幕布上的6个得分圆圈（10分、20分、30分各2个），输出每个圆圈的圆心坐标和半径，用于后续的击球计分判定。

### 1.1 两种方案

#### 方案A：OCR + HoughCircles（适用于高清静态图片）
```
OCR 定位数字中心 → HoughCircles 检测半径
```
- 适用场景：高分辨率图片（如 4032x3024）
- 代码文件：`detect_circle_size.py`

#### 方案B：Gemini + 固定半径（适用于视频帧）【推荐】
```
预处理(裁剪+放大) → Gemini 粗定位 → 固定半径
```
- 适用场景：视频帧（如 1920x1080）
- 代码文件：`detect_circles_final.py`

### 1.2 方案对比

| 方案 | 准确度 | 适用场景 | 依赖 |
|-----|--------|---------|-----|
| OCR + HoughCircles | 高 | 高清图片，OCR能识别所有数字 | 阿里云 OCR |
| **Gemini + 固定半径** | **高** | **视频帧，分辨率较低** | **Gemini API** |

---

## 2. 推荐方案：Gemini + 固定半径

### 2.1 核心思路

```
┌─────────────────────────────────────────────────────────────┐
│                    两阶段检测流程                            │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Step 1: 预处理                                              │
│  ┌─────────────────────────────────────┐                    │
│  │  1. 裁剪幕布区域（排除人员干扰）      │                    │
│  │  2. 放大 2 倍（提高识别精度）         │                    │
│  └─────────────────────────────────────┘                    │
│                       ↓                                     │
│  Step 2: Gemini 粗定位                                       │
│  ┌─────────────────────────────────────┐                    │
│  │  Prompt: "帮我标出图上10/20/30分的    │                    │
│  │          6个得分圆圈"                 │                    │
│  │  输出: 6个圆圈的 bounding box        │                    │
│  │  提取: 圆心坐标 (bbox 中心)          │                    │
│  └─────────────────────────────────────┘                    │
│                       ↓                                     │
│  Step 3: 添加固定半径                                        │
│  ┌─────────────────────────────────────┐                    │
│  │  10分: radius = 27px                 │                    │
│  │  20分: radius = 20px                 │                    │
│  │  30分: radius = 15px                 │                    │
│  └─────────────────────────────────────┘                    │
│                       ↓                                     │
│  Step 4: 坐标转换                                            │
│  ┌─────────────────────────────────────┐                    │
│  │  裁剪图坐标 → 原图坐标               │                    │
│  └─────────────────────────────────────┘                    │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 为什么这个方案有效

1. **预处理裁剪**：排除人员、地面等干扰，只保留幕布区域
2. **放大2倍**：提高 Gemini 对小圆圈的识别精度
3. **Gemini 定位**：语义理解能力强，能准确找到6个圆圈的位置
4. **固定半径**：视频帧中圆圈大小稳定，无需每次检测

### 2.3 关键参数

```python
# 半径配置（1920x1080 视频帧）
RADIUS_CONFIG = {
    10: 27,  # 10分圆圈最大
    20: 20,  # 20分圆圈居中
    30: 15,  # 30分圆圈最小
}

# 幕布裁剪区域（相对于图片尺寸的比例）
CROP_RATIO = {
    'x1': 0.29,  # 左边界
    'y1': 0.26,  # 上边界
    'x2': 0.68,  # 右边界
    'y2': 0.46,  # 下边界
}

# 放大倍数
SCALE = 2
```

### 2.4 Gemini Prompt

```
帮我标出图上 10 分 30 分 20 分的6个得分圆圈

返回JSON格式:
[{"box_2d": [y1, x1, y2, x2], "label": "10"}, ...]
坐标使用0-1000归一化值
```

---

## 3. 备选方案：OCR + HoughCircles

---

## 2. 算法流程

```
┌─────────────────────────────────────────────────────────────┐
│                    得分圆圈检测流程                           │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Step 1: 读取 OCR 结果                                       │
│  ┌─────────────────────────────────────┐                    │
│  │  输入: ocr_result.json               │                    │
│  │  提取: "10", "20", "30" 数字的位置    │                    │
│  │  计算: 数字边界框的中心点 (cx, cy)    │                    │
│  └─────────────────────────────────────┘                    │
│                       ↓                                     │
│  Step 2: 在数字中心周围检测圆圈                               │
│  ┌─────────────────────────────────────┐                    │
│  │  对每个数字位置:                       │                    │
│  │  1. 裁剪 ROI (中心周围 300px)         │                    │
│  │  2. 根据分数选择半径搜索范围           │                    │
│  │  3. HoughCircles 检测圆              │                    │
│  │  4. 选择最接近数字中心的圆            │                    │
│  └─────────────────────────────────────┘                    │
│                       ↓                                     │
│  Step 3: 输出结果                                            │
│  ┌─────────────────────────────────────┐                    │
│  │  输出: 6个圆圈的 (圆心, 半径, 分数)    │                    │
│  │  保存: circles_config.json           │                    │
│  └─────────────────────────────────────┘                    │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. 关键参数说明

### 3.1 不同分数的半径搜索范围

这是算法的**核心参数**，必须根据实际圆圈大小设置：

```python
if score == 10:
    min_r, max_r = 60, 120   # 10分圆圈最大
elif score == 20:
    min_r, max_r = 45, 80    # 20分圆圈居中
else:  # 30分
    min_r, max_r = 35, 70    # 30分圆圈最小
```

**参数设置原则：**
- `min_r` 略小于实际半径
- `max_r` 略大于实际半径
- 范围不宜过宽，否则容易检测到干扰圆

### 3.2 HoughCircles 参数

```python
circles = cv2.HoughCircles(
    roi,
    cv2.HOUGH_GRADIENT,
    dp=1,           # 累加器分辨率与图像分辨率的比值
    minDist=50,     # 圆心之间的最小距离
    param1=100,     # Canny 边缘检测的高阈值
    param2=30,      # 累加器阈值（越小检测到越多圆）
    minRadius=min_r,
    maxRadius=max_r
)
```

| 参数 | 作用 | 调整建议 |
|-----|------|---------|
| `dp` | 累加器分辨率 | 保持 1，精度最高 |
| `minDist` | 圆心最小距离 | 50 足够，防止重复检测 |
| `param1` | Canny 高阈值 | 80-120，太低会有噪声 |
| `param2` | 累加器阈值 | 20-40，太低检测过多，太高漏检 |
| `minRadius` | 最小半径 | 根据分数动态设置 |
| `maxRadius` | 最大半径 | 根据分数动态设置 |

### 3.3 搜索区域大小

```python
search_radius = 300  # 在数字中心周围 300px 范围内搜索
```

- 太小：可能截断圆圈边缘
- 太大：增加计算量和干扰
- 300px 适合大多数情况

---

## 4. 检测结果示例

### 4.1 实际检测输出

```
10分圆圈: 中心(1414, 1069), 半径  74px
10分圆圈: 中心(2252, 1047), 半径  75px
30分圆圈: 中心(1668, 1253), 半径  43px
30分圆圈: 中心(2017, 1239), 半径  40px
20分圆圈: 中心(1203, 1370), 半径  61px
20分圆圈: 中心(2465, 1344), 半径  51px
```

### 4.2 圆圈布局

```
        ┌─────────────────────────────────┐
        │           幕布区域               │
        │                                 │
        │    [10]              [10]       │  ← 第1行：10分（最大）
        │                                 │
        │         [30]    [30]            │  ← 第2行：30分（最小）
        │                                 │
        │    [20]              [20]       │  ← 第3行：20分（居中）
        │                                 │
        └─────────────────────────────────┘
```

---

## 5. 代码实现

### 5.1 核心代码 (detect_circle_size.py)

```python
# -*- coding: utf-8 -*-
"""
得分圆圈检测算法
核心思路：OCR 定位数字中心 + HoughCircles 检测半径
"""
import cv2
import json
import numpy as np

IMAGE_PATH = "IMG_9197.jpg"
OCR_RESULT_PATH = "output/ocr_result.json"
OUTPUT_PATH = "output/detected_circles.jpg"

# 读取图片
img = cv2.imread(IMAGE_PATH)
gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

# 读取 OCR 结果
with open(OCR_RESULT_PATH, 'r', encoding='utf-8') as f:
    ocr_result = json.load(f)

# 提取计分数字的位置
score_numbers = ['10', '20', '30']
score_positions = []

blocks = ocr_result['Data']['SubImages'][0]['BlockInfo']['BlockDetails']

for block in blocks:
    content = block['BlockContent']
    if content in score_numbers:
        points = block['BlockPoints']
        xs = [p['X'] for p in points]
        ys = [p['Y'] for p in points]
        cx = sum(xs) // len(xs)  # 数字中心 X
        cy = sum(ys) // len(ys)  # 数字中心 Y

        score_positions.append({
            'score': int(content),
            'center': (cx, cy),
        })

# 在每个数字中心周围搜索圆圈
detected_circles = []

for pos in score_positions:
    cx, cy = pos['center']
    score = pos['score']

    # 裁剪搜索区域
    search_radius = 300
    x1 = max(0, cx - search_radius)
    y1 = max(0, cy - search_radius)
    x2 = min(img.shape[1], cx + search_radius)
    y2 = min(img.shape[0], cy + search_radius)

    roi = gray[y1:y2, x1:x2]

    # 【关键】根据分数设置不同的半径范围
    if score == 10:
        min_r, max_r = 60, 120   # 10分圆圈最大
    elif score == 20:
        min_r, max_r = 45, 80    # 20分圆圈居中
    else:  # 30分
        min_r, max_r = 35, 70    # 30分圆圈最小

    # HoughCircles 检测
    circles = cv2.HoughCircles(
        roi,
        cv2.HOUGH_GRADIENT,
        dp=1,
        minDist=50,
        param1=100,
        param2=30,
        minRadius=min_r,
        maxRadius=max_r
    )

    if circles is not None:
        circles = np.uint16(np.around(circles))
        local_cx = cx - x1
        local_cy = cy - y1

        # 找最接近数字中心的圆
        best_circle = None
        best_dist = float('inf')

        for circle in circles[0]:
            dist = np.sqrt((circle[0] - local_cx)**2 + (circle[1] - local_cy)**2)
            if dist < best_dist:
                best_dist = dist
                best_circle = circle

        if best_circle is not None and best_dist < 100:
            real_cx = best_circle[0] + x1
            real_cy = best_circle[1] + y1
            radius = best_circle[2]

            detected_circles.append({
                'score': score,
                'center': [int(real_cx), int(real_cy)],
                'radius': int(radius),
            })
```

---

## 6. OCR 结果格式

算法依赖的 OCR 结果格式（来自阿里云 OCR 服务）：

```json
{
  "Data": {
    "SubImages": [
      {
        "BlockInfo": {
          "BlockDetails": [
            {
              "BlockContent": "10",
              "BlockPoints": [
                {"X": 1380, "Y": 1040},
                {"X": 1448, "Y": 1040},
                {"X": 1448, "Y": 1098},
                {"X": 1380, "Y": 1098}
              ]
            }
          ]
        }
      }
    ]
  }
}
```

**提取数字中心的计算：**
```python
xs = [p['X'] for p in points]  # [1380, 1448, 1448, 1380]
ys = [p['Y'] for p in points]  # [1040, 1040, 1098, 1098]
cx = sum(xs) // len(xs)        # (1380+1448+1448+1380) / 4 = 1414
cy = sum(ys) // len(ys)        # (1040+1040+1098+1098) / 4 = 1069
```

---

## 7. 输出配置文件格式

检测结果保存为 `circles_config.json`：

```json
[
  {"score": 10, "center": [1414, 1069], "radius": 74},
  {"score": 10, "center": [2252, 1047], "radius": 75},
  {"score": 20, "center": [1203, 1370], "radius": 61},
  {"score": 20, "center": [2465, 1344], "radius": 51},
  {"score": 30, "center": [1668, 1253], "radius": 43},
  {"score": 30, "center": [2017, 1239], "radius": 40}
]
```

---

## 8. 常见问题排查

### 8.1 某个分数的圆圈检测不到

**原因：** `minRadius` 或 `maxRadius` 设置不合理

**解决：**
1. 手动测量实际圆圈半径
2. 调整对应分数的 `min_r, max_r` 范围

### 8.2 检测到错误的圆

**原因：** 半径范围太宽，检测到了其他干扰圆

**解决：**
1. 缩小 `min_r, max_r` 范围
2. 增大 `param2`（累加器阈值）
3. 减小 `search_radius`（搜索范围）

### 8.3 圆心位置有偏移

**原因：** OCR 定位不准或 HoughCircles 检测偏移

**解决：**
1. 检查 OCR 结果是否正确
2. 降低 `param2` 以检测更多候选圆
3. 使用 `best_dist < 100` 过滤偏移过大的结果

---

## 9. 文件清单

| 文件 | 作用 |
|-----|------|
| `detect_circle_size.py` | 主算法代码 |
| `output/ocr_result.json` | OCR 检测结果（输入） |
| `output/detected_circles.jpg` | 可视化结果 |
| `circles_config.json` | 圆圈配置（输出） |

---

## 10. 版本历史

| 日期 | 版本 | 修改内容 |
|-----|------|---------|
| 2024-12-15 | v1.0 | 初版：统一半径范围 40-200px |
| 2024-12-15 | v1.1 | 优化：根据分数设置不同半径范围，解决30分检测不准问题 |

---

## 11. 总结

**算法核心要点：**

1. **OCR 定位是关键** - 数字位于圆心，OCR 精度高
2. **分数决定半径范围** - 10分最大，30分最小，必须分别设置
3. **选择最近的圆** - 在检测到多个圆时，选择最接近数字中心的

**记住这个公式：**
```
准确的圆心（OCR）+ 合适的半径范围 = 精确的圆圈检测
```
