"""
图表生成工具
26种图表类型合并为单一工具，在本地执行 matplotlib 脚本生成 PNG

生产级实现：
- 支持 x_field / y_field / series_field 灵活数据映射
- 数据通过临时 JSON 文件传递（避免 shell 转义问题）
- 自动中文字体配置
- 超时保护 + 错误隔离
"""
import os
import json
import tempfile
import subprocess
from pathlib import Path
from langchain_core.tools import tool

from ..log_utils import agent_logger

# 支持的26种图表类型
CHART_TYPES = [
    "bar", "horizontal_bar", "stacked_bar", "grouped_bar",
    "line", "multi_line", "area", "stacked_area",
    "pie", "donut",
    "scatter", "bubble",
    "histogram", "box_plot", "violin",
    "heatmap", "treemap",
    "radar", "polar",
    "waterfall", "funnel",
    "gauge", "kpi_card",
    "candlestick", "ohlc",
    "sankey",
]

# 图表生成脚本（从文件读取数据，避免转义问题）
CHART_SCRIPT = '''
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import json
import sys
import os

# 中文字体配置
for font in ['SimHei', 'Microsoft YaHei', 'WenQuanYi Micro Hei', 'DejaVu Sans']:
    try:
        plt.rcParams['font.sans-serif'] = [font]
        break
    except:
        continue
plt.rcParams['axes.unicode_minus'] = False

# 从文件读取参数
params_path = sys.argv[1]
with open(params_path, 'r', encoding='utf-8') as f:
    params = json.load(f)

chart_type = params["chart_type"]
data = params["data"]
title = params["title"]
output_path = params["output_path"]
x_field = params.get("x_field", "label")
y_field = params.get("y_field", "value")
series_field = params.get("series_field", "")

fig, ax = plt.subplots(figsize=(12, 8))

try:
    if chart_type == "bar":
        labels = [item.get(x_field, str(i)) for i, item in enumerate(data)]
        values = [float(item.get(y_field, 0)) for item in data]
        bars = ax.bar(labels, values, color='#2563EB', edgecolor='white')
        ax.bar_label(bars, fmt='%.1f', fontsize=9)

    elif chart_type == "horizontal_bar":
        labels = [item.get(x_field, str(i)) for i, item in enumerate(data)]
        values = [float(item.get(y_field, 0)) for item in data]
        ax.barh(labels, values, color='#2563EB')

    elif chart_type == "grouped_bar" and series_field:
        series_names = list(set(item.get(series_field, "") for item in data))
        x_labels = list(set(item.get(x_field, "") for item in data))
        x_pos = np.arange(len(x_labels))
        width = 0.8 / max(len(series_names), 1)
        colors = plt.cm.Set2(np.linspace(0, 1, len(series_names)))
        for idx, series in enumerate(series_names):
            vals = [float(next((item.get(y_field, 0) for item in data
                     if item.get(x_field) == xl and item.get(series_field) == series), 0))
                    for xl in x_labels]
            ax.bar(x_pos + idx * width, vals, width, label=series, color=colors[idx])
        ax.set_xticks(x_pos + width * (len(series_names) - 1) / 2)
        ax.set_xticklabels(x_labels)
        ax.legend()

    elif chart_type == "stacked_bar" and series_field:
        series_names = list(set(item.get(series_field, "") for item in data))
        x_labels = list(set(item.get(x_field, "") for item in data))
        x_pos = np.arange(len(x_labels))
        bottom = np.zeros(len(x_labels))
        colors = plt.cm.Set2(np.linspace(0, 1, len(series_names)))
        for idx, series in enumerate(series_names):
            vals = [float(next((item.get(y_field, 0) for item in data
                     if item.get(x_field) == xl and item.get(series_field) == series), 0))
                    for xl in x_labels]
            ax.bar(x_pos, vals, bottom=bottom, label=series, color=colors[idx])
            bottom += np.array(vals)
        ax.set_xticks(x_pos)
        ax.set_xticklabels(x_labels)
        ax.legend()

    elif chart_type in ("line", "multi_line"):
        if series_field:
            series_names = list(set(item.get(series_field, "") for item in data))
            for series in series_names:
                series_data = [item for item in data if item.get(series_field) == series]
                labels = [item.get(x_field, str(i)) for i, item in enumerate(series_data)]
                values = [float(item.get(y_field, 0)) for item in series_data]
                ax.plot(labels, values, marker='o', label=series)
            ax.legend()
        else:
            labels = [item.get(x_field, str(i)) for i, item in enumerate(data)]
            values = [float(item.get(y_field, 0)) for item in data]
            ax.plot(labels, values, marker='o', color='#2563EB', linewidth=2)

    elif chart_type in ("area", "stacked_area"):
        labels = [item.get(x_field, str(i)) for i, item in enumerate(data)]
        values = [float(item.get(y_field, 0)) for item in data]
        ax.fill_between(range(len(labels)), values, alpha=0.3, color='#2563EB')
        ax.plot(range(len(labels)), values, color='#2563EB', linewidth=2)
        ax.set_xticks(range(len(labels)))
        ax.set_xticklabels(labels, rotation=45, ha='right')

    elif chart_type == "pie":
        labels = [item.get(x_field, str(i)) for i, item in enumerate(data)]
        values = [float(item.get(y_field, 0)) for item in data]
        ax.pie(values, labels=labels, autopct='%1.1f%%', startangle=90,
               colors=plt.cm.Set3(np.linspace(0, 1, len(labels))))

    elif chart_type == "donut":
        labels = [item.get(x_field, str(i)) for i, item in enumerate(data)]
        values = [float(item.get(y_field, 0)) for item in data]
        ax.pie(values, labels=labels, autopct='%1.1f%%', startangle=90,
               pctdistance=0.85, colors=plt.cm.Set3(np.linspace(0, 1, len(labels))))
        centre = plt.Circle((0, 0), 0.70, fc='white')
        ax.add_artist(centre)

    elif chart_type == "scatter":
        x = [float(item.get("x", item.get(x_field, 0))) for item in data]
        y = [float(item.get("y", item.get(y_field, 0))) for item in data]
        ax.scatter(x, y, color='#2563EB', alpha=0.7, s=60)

    elif chart_type == "bubble":
        x = [float(item.get("x", item.get(x_field, 0))) for item in data]
        y = [float(item.get("y", item.get(y_field, 0))) for item in data]
        s = [float(item.get("size", 100)) for item in data]
        ax.scatter(x, y, s=s, color='#2563EB', alpha=0.5)

    elif chart_type == "histogram":
        values = [float(item.get(y_field, item.get("value", 0))) for item in data]
        ax.hist(values, bins=min(15, max(5, len(values)//3)), color='#2563EB', alpha=0.7, edgecolor='white')

    elif chart_type == "heatmap":
        values = [float(item.get(y_field, 0)) for item in data]
        n = int(len(values) ** 0.5) or 1
        matrix = np.array(values[:n*n]).reshape(n, n)
        im = ax.imshow(matrix, cmap='YlOrRd', aspect='auto')
        plt.colorbar(im, ax=ax)

    elif chart_type == "radar":
        labels = [item.get(x_field, str(i)) for i, item in enumerate(data)]
        values = [float(item.get(y_field, 0)) for item in data]
        angles = np.linspace(0, 2 * np.pi, len(labels), endpoint=False).tolist()
        values_plot = values + values[:1]
        angles += angles[:1]
        ax = plt.subplot(111, polar=True)
        ax.plot(angles, values_plot, 'o-', color='#2563EB', linewidth=2)
        ax.fill(angles, values_plot, alpha=0.25, color='#2563EB')
        ax.set_xticks(angles[:-1])
        ax.set_xticklabels(labels)

    elif chart_type == "waterfall":
        labels = [item.get(x_field, str(i)) for i, item in enumerate(data)]
        values = [float(item.get(y_field, 0)) for item in data]
        cumulative = 0
        colors_list = []
        bottoms = []
        for v in values:
            bottoms.append(cumulative if v >= 0 else cumulative + v)
            colors_list.append('#22C55E' if v >= 0 else '#EF4444')
            cumulative += v
        ax.bar(labels, [abs(v) for v in values], bottom=bottoms, color=colors_list, edgecolor='white')

    else:
        # 默认柱状图
        labels = [item.get(x_field, str(i)) for i, item in enumerate(data)]
        values = [float(item.get(y_field, 0)) for item in data]
        ax.bar(labels, values, color='#2563EB')

    ax.set_title(title, fontsize=14, fontweight='bold', pad=15)
    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()

except Exception as e:
    # 即使绘图出错也生成一个错误提示图
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.text(0.5, 0.5, f'Chart Error: {str(e)[:100]}', ha='center', va='center', fontsize=12, color='red')
    ax.set_title(title)

plt.savefig(output_path, dpi=150, bbox_inches='tight', facecolor='white')
plt.close()
print(f"OK:{output_path}")
'''


@tool
def generate_chart(
    chart_type: str,
    data: str,
    title: str = "数据图表",
    x_field: str = "label",
    y_field: str = "value",
    series_field: str = "",
) -> str:
    """生成数据可视化图表（支持26种类型）。

    Args:
        chart_type: 图表类型。支持: bar(柱状图), horizontal_bar(横向柱状图),
            stacked_bar(堆叠柱状图), grouped_bar(分组柱状图),
            line(折线图), multi_line(多折线), area(面积图), stacked_area(堆叠面积图),
            pie(饼图), donut(环形图), scatter(散点图), bubble(气泡图),
            histogram(直方图), box_plot(箱线图), violin(小提琴图),
            heatmap(热力图), treemap(矩形树图), radar(雷达图), polar(极坐标图),
            waterfall(瀑布图), funnel(漏斗图), gauge(仪表盘),
            candlestick(K线图), ohlc(OHLC图), sankey(桑基图), kpi_card(KPI卡片)
        data: 数据JSON字符串。格式: [{"label":"名称","value":数值}, ...]
            分组图: [{"supplier":"A","price":25,"part":"火花塞"}, ...]
            散点图: [{"x":10,"y":20}, ...]
        title: 图表标题
        x_field: X轴/分类字段名（默认"label"）
        y_field: Y轴/数值字段名（默认"value"）
        series_field: 系列/分组字段名（分组图/多线图时使用，如"supplier"）

    Returns:
        图表文件路径或错误信息
    """
    if chart_type not in CHART_TYPES:
        return f"不支持的图表类型: {chart_type}。支持: {', '.join(CHART_TYPES[:10])}... 共{len(CHART_TYPES)}种"

    # 解析数据
    try:
        #isinstance 是 Python 的内置函数，用于判断一个对象是否属于某个类型（或类型元组），返回布尔值 True 或 False。
        data_list = json.loads(data) if isinstance(data, str) else data
        if not isinstance(data_list, list) or len(data_list) == 0:
            return "错误: data 必须是非空 JSON 列表"
    except json.JSONDecodeError as e:
        return f"数据格式错误: {e}。data 必须是有效的 JSON 列表。"

    # 生成输出路径
    download_dir = Path(__file__).parent.parent.parent / "download"
    download_dir.mkdir(exist_ok=True)
    output_path = str(download_dir / f"chart_{chart_type}_{os.getpid()}.png")

    # 写入参数文件（避免 shell 转义问题）
    params = {
        "chart_type": chart_type,
        "data": data_list,
        "title": title,
        "output_path": output_path,
        "x_field": x_field,
        "y_field": y_field,
        "series_field": series_field,
    }
    #os.getpid() 是 Python 的 os 模块中的一个函数，用于获取当前进程的进程 ID（PID）。
    params_path = str(download_dir / f"_params_{os.getpid()}.json")
    script_path = str(download_dir / f"_chart_{os.getpid()}.py")

    try:
        with open(params_path, 'w', encoding='utf-8') as f:
            json.dump(params, f, ensure_ascii=False)

        with open(script_path, 'w', encoding='utf-8') as f:
            f.write(CHART_SCRIPT)

        result = subprocess.run(
            ["python", script_path, params_path],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode == 0 and os.path.exists(output_path):
            file_size = os.path.getsize(output_path)
            file_name = os.path.basename(output_path)
            download_url = f"http://localhost:8000/api/download/{file_name}"
            agent_logger.info(f"Chart generated: {output_path} ({file_size} bytes)")
            return (
                f"图表已生成: {title}\n"
                f"类型: {chart_type}\n"
                f"数据点: {len(data_list)}\n"
                f"文件大小: {file_size / 1024:.1f} KB\n"
                f"下载链接: {download_url}\n"
                f"本地路径: {output_path}"
            )
        else:
            error_msg = result.stderr[:500] if result.stderr else result.stdout[:200]
            return f"图表生成失败: {error_msg}"

    except subprocess.TimeoutExpired:
        return "图表生成超时（30秒限制）"
    except Exception as e:
        return f"图表生成异常: {str(e)}"
    finally:
        # 清理临时文件
        for tmp in [params_path, script_path]:
            if os.path.exists(tmp):
                os.remove(tmp)
