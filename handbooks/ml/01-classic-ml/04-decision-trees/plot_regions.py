"""Построить SVG-карты областей прогноза для учебных деревьев."""
from pathlib import Path

from sklearn.tree import DecisionTreeRegressor

def make_minutes(h, c, shape):
    area = 20 * h + 10 * h * (c >= 3) + 10 * shape
    return 8 + 0.1 * area + 3 * (c - 1)

train = [(h, c, shape)
         for h in range(2, 13)
         for c in range(1, 5)
         for shape in (-2, 0, 2)]
features = [(h, c) for h, c, _ in train]
answers = [make_minutes(h, c, shape) for h, c, shape in train]
large_models = {
    depth: DecisionTreeRegressor(max_depth=depth, random_state=0).fit(
        features, answers
    )
    for depth in (2, 4)
}

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import PatchCollection
from matplotlib.patches import Rectangle
from matplotlib.colors import Normalize
import numpy as np

heights = np.linspace(2, 12, 401)
grid = np.array([(h, c) for c in range(1, 5) for h in heights])
# BEGIN HANDBOOK SVG STYLE
from xml.etree import ElementTree as ET
import re
STYLE_ID = 'handbook-style'
DEFS_ID = 'handbook-defs'
CSS = ":root { color-scheme:light dark; --figure-scale:1; --ink:#1b2430; --muted:#55657a; --axis:#7a8a9c; --grid:#d5dee8; --edge:#c9d4e0; --blue:#2459c2; --blue-bg:#e8f0ff; --purple:#7238c4; --purple-bg:#f2eaff; --orange:#b05300; --orange-bg:#fff2e3; --green:#188038; --green-bg:#e6f4ea; --red:#c53929; --red-bg:#fce8e6; --yellow:#8a5a00; --yellow-bg:#fef4ce; --paper:#ffffff; --panel:none; }\n@media (prefers-color-scheme:dark) { :root { --ink:#e3e8ee; --muted:#aab6c4; --axis:#8796a7; --grid:#3d4855; --edge:#46525f; --blue:#8cbcff; --blue-bg:#1e2c42; --purple:#c7a9ff; --purple-bg:#2d2442; --orange:#ffbd6b; --orange-bg:#3a2b1a; --green:#81c995; --green-bg:#1c3326; --red:#ff9a8a; --red-bg:#3a2227; --yellow:#fdd663; --yellow-bg:#382f18; --paper:#212529; --panel:none; } }\n@media print { :root { color-scheme:light; --ink:#1b2430; --muted:#55657a; --axis:#7a8a9c; --grid:#d5dee8; --edge:#c9d4e0; --blue:#2459c2; --blue-bg:#e8f0ff; --purple:#7238c4; --purple-bg:#f2eaff; --orange:#b05300; --orange-bg:#fff2e3; --green:#188038; --green-bg:#e6f4ea; --red:#c53929; --red-bg:#fce8e6; --yellow:#8a5a00; --yellow-bg:#fef4ce; --paper:#ffffff; --panel:none; } }\nsvg { fill:var(--ink); font-family:'PT Sans','DejaVu Sans',Arial,sans-serif; font-size:calc(20px * var(--figure-scale)); }\ntext, tspan { font-family:'PT Sans','DejaVu Sans',Arial,sans-serif; }\n.s, .small { font-size:calc(16px * var(--figure-scale)); }\n.heading, .label { font-size:calc(22px * var(--figure-scale)); font-weight:700; }\n.b, .bold { font-weight:700; } .m { fill:var(--muted); } .i { font-style:italic; }\n.big { font-size:32px; font-weight:700; }\n.blue { fill:var(--blue); }\n.purple { fill:var(--purple); }\n.orange { fill:var(--orange); }\n.green { fill:var(--green); }\n.red { fill:var(--red); }\n.yellow { fill:var(--yellow); }\n.axis { fill:none; stroke:var(--axis); stroke-width:1.25; }\n.grid { fill:none; stroke:var(--grid); stroke-width:0.75; }\n.block { rx:6; stroke-width:2; }\n.flow { fill:none; stroke:var(--axis); stroke-width:2; marker-end:url(#handbook-arrow); }\n"
DEFS = '<defs xmlns="http://www.w3.org/2000/svg" id="handbook-defs">\n  <marker id="handbook-arrow" markerWidth="8" markerHeight="8" refX="7" refY="4"\n          orient="auto" markerUnits="userSpaceOnUse">\n    <path d="M0 0L8 4L0 8Z" fill="var(--axis)"/>\n  </marker>\n</defs>'
COLOR_ROLES = {'#1b2430': 'ink', '#55657a': 'muted', '#7a8a9c': 'axis', '#d5dee8': 'grid', '#c9d4e0': 'edge', '#2459c2': 'blue', '#e8f0ff': 'blue-bg', '#7238c4': 'purple', '#f2eaff': 'purple-bg', '#b05300': 'orange', '#fff2e3': 'orange-bg', '#188038': 'green', '#e6f4ea': 'green-bg', '#c53929': 'red', '#fce8e6': 'red-bg', '#8a5a00': 'yellow', '#fef4ce': 'yellow-bg', '#000000': 'ink', '#262626': 'ink', '#2563eb': 'blue', '#ea580c': 'orange', '#cbd5e1': 'grid'}
SIZES = {'body': 20, 'small': 16, 'heading': 22, 'grid': 8, 'padding': 16, 'gap': 24, 'radius': 6, 'line': 2, 'axis': 1.25, 'grid_line': 0.75}

def normalize_svg(source):
    """Обновить только отмеченный стиль и общие маркеры, не меняя рисунок."""
    ET.register_namespace('', 'http://www.w3.org/2000/svg')
    ET.register_namespace('xlink', 'http://www.w3.org/1999/xlink')
    root = ET.fromstring(source)
    if root.tag != '{http://www.w3.org/2000/svg}svg':
        raise ValueError('Ожидался корневой SVG')
    for node in list(root):
        if node.get('id') in (STYLE_ID, DEFS_ID):
            root.remove(node)
    style = ET.Element('{http://www.w3.org/2000/svg}style', {'id': STYLE_ID})
    style.text = '\n' + CSS
    index = next((i for i, node in enumerate(root)
                  if node.tag.rsplit('}', 1)[-1] not in ('title', 'desc')), len(root))
    root.insert(index, style)
    root.insert(index + 1, ET.fromstring(DEFS))
    # Preserve mixed text exactly: indentation must not insert spaces into math.
    mixed = [(node, node.text, node.tail) for text in root.iter()
             if text.tag.rsplit('}', 1)[-1] == 'text' for node in text.iter()]
    ET.indent(root, space='  ')
    for node, text, tail in mixed:
        node.text, node.tail = text, tail
    return ET.tostring(root, encoding='unicode') + '\n'

def apply_matplotlib_style(plt, width=560):
    """Размеры заданы в единицах SVG, экспортируемых Matplotlib как пункты."""
    scale = width / 560
    plt.rcParams.update({
        'font.family': 'DejaVu Sans', 'font.size': SIZES['body'] * scale,
        'axes.titlesize': SIZES['heading'] * scale, 'axes.titleweight': 'bold',
        'axes.labelsize': SIZES['body'] * scale, 'xtick.labelsize': SIZES['small'] * scale,
        'ytick.labelsize': SIZES['small'] * scale, 'legend.fontsize': SIZES['small'] * scale,
        'axes.linewidth': SIZES['axis'] * scale, 'grid.linewidth': SIZES['grid_line'] * scale,
        'svg.fonttype': 'none', 'svg.hashsalt': 'beloai-classroom',
    })

def finish_plot(path, title, description):
    root = ET.fromstring(path.read_bytes())
    for node in list(root):
        if node.tag.rsplit('}', 1)[-1] in ('metadata', 'title', 'desc') or node.get('id') == STYLE_ID:
            root.remove(node)
    for parent in root.iter():
        for node in list(parent):
            if node.tag.endswith('path') and node.get('style', '').strip() == 'fill: #ffffff':
                parent.remove(node)
    for node in root.iter():
        for attribute in ('fill', 'stroke'):
            value = node.get(attribute, '').lower()
            if value in COLOR_ROLES:
                node.set(attribute, 'var(--' + COLOR_ROLES[value] + ')')
        if 'style' in node.attrib:
            style = re.sub(r'#[0-9a-fA-F]{6}\b', lambda m: 'var(--' + COLOR_ROLES[m[0].lower()] + ')'
                           if m[0].lower() in COLOR_ROLES else m[0], node.get('style'))
            node.set('style', re.sub(r'font-family:[^;]+', "font-family:'PT Sans','DejaVu Sans',Arial,sans-serif", style))
    _, _, width, height = root.get('viewBox').split()
    root.set('width', width)
    root.set('height', height)
    root.set('style', f'--figure-scale:{float(width) / 560:g}')
    root.set('role', 'img')
    root.set('aria-labelledby', 'title desc')
    for index, (name, value) in enumerate((('title', title), ('desc', description))):
        node = ET.Element('{http://www.w3.org/2000/svg}' + name, {'id': name})
        node.text = value
        root.insert(index, node)
    path.write_text(normalize_svg(ET.tostring(root, encoding='unicode')), encoding='utf-8')

# END HANDBOOK SVG STYLE

# Размер текста определяется одной панелью, а не суммарной шириной пары.
apply_matplotlib_style(plt, width=672)
fig, axes = plt.subplots(1, 2, figsize=(1120 / 72, 400 / 72), sharex=True, sharey=True, layout="constrained")

for ax, depth in zip(axes, (2, 4)):
    forecasts = large_models[depth].predict(grid).reshape(4, -1)
    # Объединяем соседние ячейки одного прогноза в векторные области.
    # Границы совпадают с ячейками исходной сетки из 401 значения.
    patches, values = [], []
    for row_index, row in enumerate(forecasts):
        edges = np.r_[0, np.flatnonzero(np.diff(row)) + 1, len(row)]
        for start, end in zip(edges[:-1], edges[1:]):
            patches.append(Rectangle((2 + start * 10 / len(row), row_index + 0.5),
                                     (end - start) * 10 / len(row), 1))
            values.append(row[start])
    picture = PatchCollection(patches, cmap="viridis", norm=Normalize(12, 52),
                              edgecolor="face", linewidth=0)
    picture.set_array(np.array(values))
    ax.add_collection(picture)
    ax.set(xlim=(2, 12), ylim=(0.5, 4.5))
    ax.scatter([h for h in range(2, 13) for c in range(1, 5)],
               [c for h in range(2, 13) for c in range(1, 5)],
               s=12, facecolors="none", edgecolors="white", linewidths=0.6)
    ax.set(title=f"Глубина {depth}", xlabel="Высота, см",
           yticks=(1, 2, 3, 4))
for ax in axes:
    ax.set_ylabel("Число цветов")
    ax.tick_params(labelbottom=True, labelleft=True)
colorbar = fig.colorbar(picture, ax=axes, label="Прогноз, мин")
colorbar.solids.set_rasterized(False)
output = Path(__file__).parent / "media/decision-regions.svg"
fig.savefig(output, transparent=True, metadata={"Date": None})
plt.close(fig)

finish_plot(output, 'Области прогноза двух деревьев', 'Карты прогноза времени печати по высоте и числу цветов. Слева дерево глубины 2, справа глубины 4. Светлые и тёмные области соответствуют значениям цветовой шкалы в минутах.')
