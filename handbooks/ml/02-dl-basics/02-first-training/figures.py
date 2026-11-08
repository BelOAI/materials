"""Построить рисунки параграфа: python3 figures.py (SVG появятся в media/).

Рисунки собираются как SVG вручную: прозрачный фон, цвета через CSS-переменные
для светлой, тёмной и печатной темы. Картинки цифр, кривая ошибки, вероятности
и примеры ошибок берутся из тех же моделей и разбиений, что и текст параграфа
(те же random_state, результат повторяется). Нужны numpy и scikit-learn.
"""
from html import escape
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
MEDIA = HERE / "media"

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

# Общая палитра и размеры задаются блоком выше; здесь только локальные классы рисунков.
LOCAL_STYLE = ".muted { fill:var(--muted); } .italic { font-style:italic; } " \
              ".tiny { font-size:calc(13px * var(--figure-scale)); }"
SCALE = 0.75  # основной текст 15, мелкий 12 единиц: под эту типографику свёрстаны рисунки
ROLE = {"line": "edge", "blue-tint": "blue-bg", "orange-tint": "orange-bg",
        "green-tint": "green-bg", "red-tint": "red-bg"}


def var(name):
    return f"var(--{ROLE.get(name, name)})"


COLORS = ["ink", "muted", "blue", "orange", "green", "red", "axis"]


def num(x, digits=2):
    return f"{x:.{digits}f}".rstrip("0").rstrip(".").replace(".", ",").replace("-", "−")


class Figure:
    def __init__(self, width, height, title, desc):
        self.width, self.height, self.title, self.desc = width, height, title, desc
        self.items = []

    def text(self, x, y, s, cls="", anchor="start"):
        cls = f' class="{cls}"' if cls else ""
        self.items.append(f'<text x="{x:.1f}" y="{y:.1f}" text-anchor="{anchor}"{cls}>{s}</text>')

    def rect(self, x, y, w, h, fill="none", stroke="line", rx=6, width=1.5, opacity=1):
        fill = fill if fill == "none" else var(fill)
        stroke = stroke if stroke == "none" else var(stroke)
        extra = f' opacity="{opacity:.3f}"' if opacity != 1 else ""
        self.items.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{rx}" '
                          f'fill="{fill}" stroke="{stroke}" stroke-width="{width}"{extra}/>')

    def line(self, x1, y1, x2, y2, color="axis", width=1.5, dash=None, arrow=False, opacity=1):
        extra = f' stroke-dasharray="{dash}"' if dash else ""
        extra += f' marker-end="url(#arrow-{color})"' if arrow else ""
        extra += f' opacity="{opacity}"' if opacity != 1 else ""
        self.items.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
                          f'stroke="{var(color)}" stroke-width="{width}"{extra}/>')

    def path(self, d, color="axis", width=1.5, arrow=False, dash=None):
        extra = f' marker-end="url(#arrow-{color})"' if arrow else ""
        extra += f' stroke-dasharray="{dash}"' if dash else ""
        self.items.append(f'<path d="{d}" fill="none" stroke="{var(color)}" stroke-width="{width}"{extra}/>')

    def circle(self, x, y, r=5, color="blue", fill=None):
        fill = var(color) if fill is None else (fill if fill == "none" else var(fill))
        self.items.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r}" fill="{fill}" '
                          f'stroke="{var(color)}" stroke-width="1.5"/>')

    def cell(self, x, y, s, w=40, h=34, fill="none", stroke="line", cls=""):
        self.rect(x, y, w, h, fill=fill, stroke=stroke, rx=4)
        self.text(x + w / 2, y + h / 2 + 5, s, cls=cls, anchor="middle")

    def picture(self, image, x, y, side):
        """Картинка 8 на 8: яркость точки задаёт прозрачность чернил."""
        step = side / image.shape[0]
        for i, row in enumerate(image):
            for j, value in enumerate(row):
                if value > 0:
                    self.rect(x + j * step, y + i * step, step + 0.3, step + 0.3,
                              fill="ink", stroke="none", rx=0, opacity=float(value) / 16)
        self.rect(x, y, side, side, stroke="line", rx=3, width=1.25)

    def save(self, name):
        markers = "".join(
            f'<marker id="arrow-{c}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" '
            f'orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" fill="{var(c)}"/></marker>'
            for c in COLORS)
        body = "\n  ".join(self.items)
        svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.width}" height="{self.height}" '
               f'viewBox="0 0 {self.width} {self.height}" style="--figure-scale:{SCALE:g}" '
               f'role="img" aria-labelledby="title desc">\n'
               f'  <title id="title">{escape(self.title)}</title>\n'
               f'  <desc id="desc">{escape(self.desc)}</desc>\n'
               f'  <style>{LOCAL_STYLE}</style>\n'
               f'  <defs>{markers}</defs>\n  {body}\n</svg>\n')
        # normalize_svg из общего блока добавляет палитру, шрифты и тёмную тему.
        (MEDIA / f"{name}.svg").write_text(normalize_svg(svg), encoding="utf-8")


# --- данные и модели: те же, что в тексте -----------------------------------
def experiments():
    from sklearn.datasets import load_digits
    from sklearn.model_selection import train_test_split
    from sklearn.neural_network import MLPClassifier

    digits = load_digits()
    mask = (digits.target == 3) | (digits.target == 8)
    X = digits.data[mask] / 16
    y = (digits.target[mask] == 8).astype(int)
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.3, random_state=0, stratify=y)
    net = MLPClassifier(hidden_layer_sizes=(16,), max_iter=200, random_state=0)
    net.fit(X_train, y_train)

    binary_proba = net.predict_proba(X_test)[:, 1]
    binary_wrong = [(X_test[i].reshape(8, 8) * 16, float(binary_proba[i]))
                    for i in np.where(net.predict(X_test) != y_test)[0]]

    X_all, y_all = digits.data / 16, digits.target
    Xa_train, Xa_test, ya_train, ya_test = train_test_split(
        X_all, y_all, test_size=0.3, random_state=0, stratify=y_all)
    net10 = MLPClassifier(hidden_layer_sizes=(32,), max_iter=200, random_state=0)
    net10.fit(Xa_train, ya_train)
    predicted = net10.predict(Xa_test)
    probabilities = net10.predict_proba(Xa_test)
    return {
        "three": digits.images[3],
        "binary_wrong": binary_wrong,
        "curve": [float(v) for v in net.loss_curve_],
        "picture": (Xa_test[0] * 16).reshape(8, 8),
        "proba": probabilities[0],
        "wrong": [(Xa_test[i].reshape(8, 8) * 16, int(ya_test[i]), int(predicted[i]),
                   float(probabilities[i].max()))
                  for i in np.where(predicted != ya_test)[0][:6]],
    }


# --- 1. от картинки к ответу сети -------------------------------------------
def fig_digit_to_net(data):
    image = data["three"]
    f = Figure(640, 250, "От картинки к ответу сети",
               "Картинка 8 на 8 с тройкой записана числами от 0 до 16; строки выписаны подряд "
               "в вектор из 64 чисел, который подан на входы сети из 64 входов, 16 нейронов "
               "скрытого слоя и одного выхода с вероятностью восьмёрки.")
    f.text(62, 28, "картинка 8 × 8", "muted small", "middle")
    f.picture(image, 20, 46, 84)
    f.text(62, 152, "числа от 0 до 16", "muted tiny", "middle")

    f.line(114, 88, 142, 88, color="axis", arrow=True)

    x0, w = 154, 34
    f.text(x0 + 2.6 * w, 28, "строки выписываем подряд", "muted small", "middle")
    flat = image.reshape(-1)
    for k in range(5):
        f.cell(x0 + k * w, 68, str(int(flat[k])), w=w - 4, h=40, cls="small")
    f.text(x0 + 5 * w + 6, 93, "…", anchor="middle")
    f.text(x0 + 2.6 * w, 136, "64 числа, затем делим на 16", "muted tiny", "middle")

    f.line(x0 + 5.5 * w, 88, x0 + 6.4 * w, 88, color="axis", arrow=True)

    f.text(500, 28, "сеть 64 — 16 — 1", "muted small", "middle")
    layers = [(400, "64 входа"), (492, "16 нейронов")]
    rows = [68, 100, 132]
    for x, label in layers:
        for y in rows:
            f.circle(x, y, 9, color="blue", fill="blue-tint")
        f.text(x, 168, "⋮", "muted", "middle")
        f.text(x, 206, label, "muted tiny", "middle")
    for y1 in rows:
        for y2 in rows:
            f.line(409, y1, 483, y2, color="grid", width=0.8)
    for y1 in rows:
        f.line(501, y1, 573, 100, color="grid", width=0.8)
    f.circle(584, 100, 11, color="orange", fill="orange-tint")
    f.text(584, 148, "вероятность", "orange tiny", "middle")
    f.text(584, 168, "восьмёрки", "orange tiny", "middle")
    f.save("digit-to-net")


# --- 2. ошибки на тройках и восьмёрках --------------------------------------
def fig_binary_mistakes(data):
    items = data["binary_wrong"]
    f = Figure(460, 214, "Две картинки, на которых сеть ошиблась",
               "Две картинки 8 на 8 из проверочной части: обе — тройки, которые сеть приняла "
               f"за восьмёрки с вероятностями {num(items[0][1])} и {num(items[1][1])}.")
    f.text(230, 28, "обе картинки — тройки", "muted small", "middle")
    side, gap = 92, 110
    x0 = (460 - 2 * side - gap) / 2
    for index, (image, probability) in enumerate(items[:2]):
        x = x0 + index * (side + gap)
        f.picture(image, x, 48, side)
        f.text(x + side / 2, 166, "сеть: восьмёрка", "b red", "middle")
        f.text(x + side / 2, 190, f"вероятность {num(probability)}", "muted small", "middle")
    f.save("binary-mistakes")


# --- 3. цикл обучения -------------------------------------------------------
def fig_fit_loop():
    f = Figure(620, 252, "Цикл обучения внутри fit",
               "Три карточки по кругу: прогноз сети, ошибка по правильным ответам и поправка "
               "всех весов против производной. Стрелка возвращает к прогнозу. "
               "Один полный проход по всем обучающим примерам называют эпохой.")
    cards = [
        ("1. Прогноз", ["сеть считает ответы", "для обучающих картинок"], "blue"),
        ("2. Ошибка", ["сравниваем с правдой:", "штраф −ln p за ответ"], "orange"),
        ("3. Поправка", ["двигаем все 1057 весов", "против производной"], "green"),
    ]
    x0, y, w, h, gap = 12, 52, 192, 98, 16
    for index, (head, lines, color) in enumerate(cards):
        left = x0 + index * (w + gap)
        f.rect(left, y, w, h, fill=f"{color}-tint", stroke=color)
        f.text(left + w / 2, y + 32, head, f"b {color}", "middle")
        for k, line in enumerate(lines):
            f.text(left + w / 2, y + 58 + k * 21, line, "muted small", "middle")
        if index < 2:
            f.line(left + w + 2, y + h / 2, left + w + gap - 2, y + h / 2, color="axis", arrow=True)
    f.text(310, 30, "один проход по всем примерам — эпоха", "muted small", "middle")
    f.path(f"M{x0 + 2 * (w + gap) + w / 2} {y + h + 4} V{y + h + 28} H{x0 + w / 2} V{y + h + 6}",
           color="axis", arrow=True)
    f.text(310, y + h + 52, "повторяем заданное число эпох", "muted small", "middle")
    f.save("fit-loop")


# --- 4. шаг против производной ----------------------------------------------
def fig_step():
    f = Figure(600, 300, "Шаг против производной",
               "Кривая ошибки в зависимости от одного веса. В текущей точке проведена касательная "
               "с отрицательным наклоном. Небольшой шаг сдвигает вес вправо и опускает его ниже "
               "по кривой, слишком большой перелетает через самое низкое место и поднимает ошибку.")
    ox, oy, sx, sy = 70, 246, 110, 124

    def P(w, loss):
        return ox + w * sx, oy - loss * sy

    def loss(w):
        return 0.18 + 0.30 * (w - 2.2) ** 2

    f.line(ox - 12, oy, 566, oy, color="axis", arrow=True)
    f.line(ox, oy + 12, ox, 56, color="axis", arrow=True)
    f.text(556, 272, "вес w", "muted small", "end")
    f.text(ox + 6, 50, "ошибка L", "muted small", "start")

    points = " ".join(f"{P(w, loss(w))[0]:.1f},{P(w, loss(w))[1]:.1f}"
                      for w in np.linspace(0.12, 4.3, 180))
    f.items.append(f'<polyline points="{points}" fill="none" stroke="{var("blue")}" stroke-width="2.5"/>')

    w0 = 0.8
    ax, ay = P(w0, loss(w0))
    slope = 0.60 * (w0 - 2.2)
    f.line(*P(w0 - 0.45, loss(w0) + slope * (-0.45)), *P(w0 + 0.45, loss(w0) + slope * 0.45),
           color="orange", width=2, dash="7 5")
    f.circle(ax, ay, 6, color="orange")
    f.text(206, 214, "касательная:", "orange small", "end")
    f.text(206, 234, "наклон отрицателен", "orange small", "end")

    w1 = 1.6
    bx, by = P(w1, loss(w1))
    f.path(f"M{ax + 7} {ay + 7} Q{(ax + bx) / 2 - 4} {(ay + by) / 2 + 16} {bx - 5} {by - 5}",
           color="green", width=2.2, arrow=True)
    f.circle(bx, by, 5, color="green")
    f.text(bx + 26, by - 36, "небольшой шаг:", "green small")
    f.text(bx + 26, by - 16, "ошибка стала меньше", "green small")

    w2 = 3.8
    cx, cy = P(w2, loss(w2))
    f.path(f"M{ax + 10} {ay - 10} Q{(ax + cx) / 2} 66 {cx - 6} {cy - 8}",
           color="red", width=2.2, arrow=True)
    f.circle(cx, cy, 5, color="red")
    f.text(cx, cy + 26, "слишком большой шаг:", "red small", "middle")
    f.text(cx, cy + 46, "перелетели минимум", "red small", "middle")

    mx, my = P(2.2, loss(2.2))
    f.line(mx, my, mx, oy, color="grid", width=1, dash="4 4")
    f.text(mx, 272, "самое низкое место", "muted small", "middle")
    f.save("step")


# --- 5. ошибка по эпохам ----------------------------------------------------
def fig_loss_curve(data):
    curve = data["curve"]
    f = Figure(600, 290, "Ошибка по эпохам",
               f"График средней ошибки по {len(curve)} эпохам обучения: кривая начинается около "
               f"{num(curve[0])}, быстро падает в начале, затем снижается всё медленнее "
               f"и доходит примерно до {num(curve[-1])} к последней эпохе.")
    ox, oy, right, top = 86, 240, 574, 58
    top_loss = 0.8

    def P(epoch, loss):
        return ox + epoch / len(curve) * (right - ox), oy - loss / top_loss * (oy - top)

    for value in (0.2, 0.4, 0.6, 0.8):
        x, y = P(0, value)
        f.line(ox, y, right, y, color="grid", width=1)
        f.text(ox - 12, y + 5, num(value, 1), "muted small", "end")
    for epoch in (0, 50, 100, 150, 200):
        x, _ = P(epoch, 0)
        f.line(x, oy, x, oy + 6, color="axis", width=1)
        f.text(x, oy + 26, str(epoch), "muted small", "middle")
    f.line(ox, oy, right, oy, color="axis")
    f.line(ox, oy, ox, top - 8, color="axis")
    f.text(ox - 12, top - 14, "ошибка", "muted small", "end")
    f.text(right, oy + 48, "эпоха", "muted small", "end")

    points = " ".join(f"{P(i, v)[0]:.1f},{P(i, v)[1]:.1f}" for i, v in enumerate(curve))
    f.items.append(f'<polyline points="{points}" fill="none" stroke="{var("blue")}" stroke-width="2.5"/>')

    x, y = P(0, curve[0])
    f.circle(x, y, 5, color="orange")
    f.text(x + 12, y - 12, f"случайные веса: {num(curve[0])}", "orange small")
    x, y = P(len(curve) - 1, curve[-1])
    f.circle(x, y, 5, color="green")
    f.text(x - 8, y - 16, f"после обучения: {num(curve[-1])}", "green small", "end")
    f.save("loss-curve")


# --- 6. десять вероятностей -------------------------------------------------
def fig_probabilities(data):
    proba = data["proba"]
    best = int(np.argmax(proba))
    second = int(np.argsort(proba)[-2])
    f = Figure(640, 270, "Десять вероятностей для одной картинки",
               f"Слева картинка 8 на 8 с единицей, справа десять столбиков вероятностей для цифр "
               f"от 0 до 9: высокий столбик {num(proba[best])} у цифры {best}, небольшой "
               f"{num(proba[second])} у цифры {second}, остальные почти нулевые.")
    f.text(66, 30, "картинка", "muted small", "middle")
    f.picture(data["picture"], 24, 48, 84)
    f.text(66, 170, f"ответ сети: {best}", "b", "middle")

    ox, oy, bar, gap, height = 168, 212, 34, 13, 140
    f.text(168 + 5 * (bar + gap) - gap / 2, 30, "вероятности десяти цифр", "muted small", "middle")
    f.line(ox - 10, oy, ox + 10 * (bar + gap) - gap + 4, oy, color="axis")
    for digit, value in enumerate(proba):
        x = ox + digit * (bar + gap)
        tall = max(float(value) * height, 1.5)
        color = "blue" if digit == best else ("orange" if digit == second else "muted")
        f.rect(x, oy - tall, bar, tall, fill=f"{color}-tint" if color != "muted" else "none",
               stroke=color, rx=3, width=1.5)
        f.text(x + bar / 2, oy + 26, str(digit), "muted small", "middle")
        if value >= 0.01:
            f.text(x + bar / 2, oy - tall - 10, num(float(value)), f"{color} small", "middle")
    f.text(ox + 5 * (bar + gap) - gap / 2, oy + 56, "сумма вероятностей равна 1", "muted small", "middle")
    f.save("probabilities")


# --- 7. ошибки сети ---------------------------------------------------------
def fig_mistakes(data):
    items = data["wrong"]
    pairs = ", ".join(f"{true} сеть назвала {pred}" for _, true, pred, _ in items)
    f = Figure(640, 210, "Картинки, на которых сеть ошиблась",
               f"Шесть неверно распознанных картинок 8 на 8; под каждой настоящая цифра, ответ сети "
               f"и её уверенность: {pairs}.")
    f.text(320, 28, "настоящая цифра → ответ сети и уверенность", "muted small", "middle")
    side, gap = 82, 22
    total = len(items) * side + (len(items) - 1) * gap
    x0 = (640 - total) / 2
    for index, (image, true, pred, confidence) in enumerate(items):
        x = x0 + index * (side + gap)
        f.picture(image, x, 48, side)
        f.text(x + side / 2, 158, f"{true} → {pred}", "b red", "middle")
        f.text(x + side / 2, 182, num(confidence), "muted small", "middle")
    f.save("mistakes")


if __name__ == "__main__":
    MEDIA.mkdir(exist_ok=True)
    data = experiments()
    fig_digit_to_net(data)
    fig_binary_mistakes(data)
    fig_fit_loop()
    fig_step()
    fig_loss_curve(data)
    fig_probabilities(data)
    fig_mistakes(data)
    print("Готово:", ", ".join(sorted(p.name for p in MEDIA.glob("*.svg"))))
