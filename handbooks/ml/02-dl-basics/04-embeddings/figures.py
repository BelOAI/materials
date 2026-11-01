"""Построить рисунки параграфа: python3 figures.py (SVG появятся в media/).

Рисунки собираются как SVG вручную: прозрачный фон, цвета через CSS-переменные
для светлой, тёмной и печатной темы. Схема word2vec берёт вероятности из той же модели gensim,
что и текст; карта слов читает data/glove-twitter.npz и строится через t-SNE.
Нужны numpy, scikit-learn и gensim.
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
              ".sym { font-size:calc(24px * var(--figure-scale)); }"
SCALE = 0.75  # основной текст 15, мелкий 12 единиц: под эту типографику свёрстаны рисунки
ROLE = {"line": "edge", "blue-tint": "blue-bg", "orange-tint": "orange-bg", "green-tint": "green-bg"}


def var(name):
    return f"var(--{ROLE.get(name, name)})"


COLORS = ["ink", "muted", "blue", "orange", "green", "axis"]

TEXT = """кот пьёт молоко
собака пьёт воду
кот ловит мышь
собака ловит мяч
кот спит дома
собака спит дома
ракета летит высоко
самолёт летит высоко
ракета несёт спутник
самолёт несёт пассажиров"""
ANIMAL = {"кот", "собака", "пьёт", "молоко", "воду", "ловит", "мышь", "мяч", "спит", "дома"}


def num(x, digits=2):
    return f"{x:.{digits}f}".rstrip("0").rstrip(".").replace(".", ",").replace("-", "−")


class Figure:
    def __init__(self, width, height, title, desc):
        self.width, self.height, self.title, self.desc = width, height, title, desc
        self.items = []

    def text(self, x, y, s, cls="", anchor="start"):
        cls = f' class="{cls}"' if cls else ""
        self.items.append(f'<text x="{x:.1f}" y="{y:.1f}" text-anchor="{anchor}"{cls}>{s}</text>')

    def rect(self, x, y, w, h, fill="none", stroke="line", rx=6, width=1.5):
        fill = fill if fill == "none" else var(fill)
        stroke = stroke if stroke == "none" else var(stroke)
        self.items.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{rx}" '
                          f'fill="{fill}" stroke="{stroke}" stroke-width="{width}"/>')

    def line(self, x1, y1, x2, y2, color="axis", width=1.5, dash=None, arrow=False, opacity=1):
        extra = f' stroke-dasharray="{dash}"' if dash else ""
        extra += f' marker-end="url(#arrow-{color})"' if arrow else ""
        extra += f' opacity="{opacity}"' if opacity != 1 else ""
        self.items.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
                          f'stroke="{var(color)}" stroke-width="{width}"{extra}/>')

    def path(self, d, color="axis", width=1.5, arrow=False):
        extra = f' marker-end="url(#arrow-{color})"' if arrow else ""
        self.items.append(f'<path d="{d}" fill="none" stroke="{var(color)}" stroke-width="{width}"{extra}/>')

    def circle(self, x, y, r=5, color="blue"):
        self.items.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r}" fill="{var(color)}"/>')

    def cell(self, x, y, s, w=40, h=34, fill="none", stroke="line", cls=""):
        self.rect(x, y, w, h, fill=fill, stroke=stroke)
        self.text(x + w / 2, y + h / 2 + 5, s, cls=cls, anchor="middle")

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


def sqrt2(f, x, y, color):
    """Знак корня из 2: линия радикала и цифра под чертой."""
    f.path(f"M{x} {y - 7} L{x + 4} {y - 9} L{x + 9} {y + 2} L{x + 15} {y - 16} L{x + 28} {y - 16}",
           color=color, width=1.3)
    f.text(x + 16, y, "2", color)


# --- 1. one-hot -----------------------------------------------------------
def fig_onehot():
    words = ["кот", "собака", "ракета", "самолёт"]
    f = Figure(640, 230, "One-hot векторы четырёх слов",
               "Каждое слово записано вектором из нулей и одной единицы на позиции своего индекса. "
               "Для любой пары разных слов скалярное произведение равно 0, а расстояние — корню из 2.")
    x0, y0, w, h = 110, 44, 48, 38
    f.text(x0 + 2 * w, 16, "позиция в словаре", "muted small", "middle")
    for j in range(4):
        f.text(x0 + j * w + w / 2, 36, str(j), "muted small", "middle")
    for i, word in enumerate(words):
        y = y0 + i * (h + 6)
        f.text(x0 - 12, y + h / 2 + 5, word, anchor="end")
        for j in range(4):
            hot = i == j
            f.cell(x0 + j * w + 4, y, "1" if hot else "0", w=w - 8, h=h,
                   fill="blue-tint" if hot else "none", stroke="blue" if hot else "line",
                   cls="bold blue" if hot else "muted")
    f.text(345, 80, "любая пара разных слов:")
    f.text(345, 112, "скалярное произведение = 0", "orange")
    f.text(345, 144, "расстояние =", "orange")
    sqrt2(f, 460, 144, "orange")
    f.text(345, 180, "«кот» не ближе к «собаке»,", "muted small")
    f.text(345, 199, "чем к «ракете»", "muted small")
    f.save("onehot")


# --- 2. расстояние и угол ---------------------------------------------------
def fig_compare():
    f = Figure(640, 270, "Расстояние и угол между векторами",
               "Векторы a = (3, 4) и b = (4, 3) почти совпадают по направлению: расстояние между концами "
               "примерно 1,41, косинус угла 0,96. Вектор c = (−4, 3) перпендикулярен a: косинус равен 0.")
    ox, oy, s = 215, 245, 40

    def P(x, y):
        return ox + x * s, oy - y * s

    for gx in range(-4, 6):
        f.line(*P(gx, 0), *P(gx, 5.2), color="grid", width=1)
    for gy in range(0, 6):
        f.line(*P(-4.5, gy), *P(5.2, gy), color="grid", width=1)
    f.line(*P(-4.5, 0), *P(5.4, 0), color="axis", arrow=True)
    f.line(*P(0, 0), *P(0, 5.6), color="axis", arrow=True)
    ang_a, ang_b = np.arctan2(4, 3), np.arctan2(3, 4)
    r = 62
    f.path(f"M{ox + r * np.cos(ang_b):.1f} {oy - r * np.sin(ang_b):.1f} "
           f"A{r} {r} 0 0 0 {ox + r * np.cos(ang_a):.1f} {oy - r * np.sin(ang_a):.1f}", color="green", width=2.5)
    ua, uc = np.array([3, 4]) / 5 * 16, np.array([-4, 3]) / 5 * 16
    corner = ua + uc
    f.path(f"M{ox + ua[0]:.1f} {oy - ua[1]:.1f} L{ox + corner[0]:.1f} {oy - corner[1]:.1f} "
           f"L{ox + uc[0]:.1f} {oy - uc[1]:.1f}", color="muted", width=1.3)
    for (x, y), color in [((3, 4), "blue"), ((4, 3), "blue"), ((-4, 3), "muted")]:
        f.line(*P(0, 0), *P(x, y), color=color, width=2.5, arrow=True)
    f.line(*P(3, 4), *P(4, 3), color="orange", width=2.5, dash="5 4")
    ax_, ay_ = P(3, 4)
    f.text(ax_ - 10, ay_ - 4, "a", "bold blue italic", "end")
    bx_, by_ = P(4, 3)
    f.text(bx_ + 8, by_ + 6, "b", "bold blue italic")
    cx_, cy_ = P(-4, 3)
    f.text(cx_, cy_ - 10, "c", "bold muted italic", "middle")
    mx, my = P(3.5, 3.5)
    f.text(mx + 10, my - 8, "расстояние", "orange small")
    gx_, gy_ = P(1.35, 1.25)
    f.text(gx_ + 4, gy_ + 4, "угол", "green small")
    bx = 452
    f.rect(bx, 16, 180, 72, fill="orange-tint", stroke="none", rx=10)
    f.text(bx + 14, 44, "расстояние a и b", "bold")
    f.text(bx + 14, 72, "≈ 1,41")
    f.rect(bx, 98, 180, 72, fill="green-tint", stroke="none", rx=10)
    f.text(bx + 14, 126, "cos(a, b) = 0,96", "bold")
    f.text(bx + 14, 152, "почти одно направление", "small")
    f.rect(bx, 180, 180, 72, fill="blue-tint", stroke="none", rx=10)
    f.text(bx + 14, 208, "cos(a, c) = 0", "bold")
    f.text(bx + 14, 234, "прямой угол", "small")
    f.save("compare")


# --- 3. мешок слов ------------------------------------------------------------
def fig_bow():
    vocab = ["фильм", "хороший", "плохой", "очень", "скучный"]
    sentence = ["очень", "очень", "хороший", "фильм"]
    f = Figure(640, 291, "Мешок слов как сумма one-hot векторов",
               "Предложение «очень очень хороший фильм»: one-hot векторы четырёх слов складываются в мешок "
               "(1, 1, 0, 2, 0) — число вхождений каждого слова словаря. Порядок слов при этом теряется.")
    x0, y0, w, h = 170, 40, 80, 32
    f.text(x0 - 16, 26, "словарь:", "muted small", "end")
    for j, word in enumerate(vocab):
        f.text(x0 + j * w + w / 2, 26, word, "small bold", "middle")
    for i, word in enumerate(sentence):
        y = y0 + i * (h + 6)
        f.text(x0 - 16, y + h / 2 + 5, f"«{word}»", anchor="end")
        for j, v in enumerate(vocab):
            hot = v == word
            f.cell(x0 + j * w + 8, y, "1" if hot else "0", w=w - 16, h=h,
                   fill="blue-tint" if hot else "none", stroke="blue" if hot else "line",
                   cls="bold blue" if hot else "muted")
    ys = y0 + 4 * (h + 6) + 4
    f.line(x0 + 4, ys, x0 + 5 * w - 4, ys, color="ink", width=1.5)
    f.text(x0 - 16, ys + 6, "сумма", "muted small", "end")
    counts = [sentence.count(v) for v in vocab]
    for j, c in enumerate(counts):
        f.cell(x0 + j * w + 8, ys + 12, str(c), w=w - 16, h=h + 4,
               fill="orange-tint" if c else "none", stroke="orange" if c else "line",
               cls="bold orange sym" if c else "muted")
    f.text(x0 - 16, ys + 12 + (h + 4) / 2 + 6, "мешок", "bold orange", "end")
    f.text(320, ys + 84, "«фильм хороший очень очень» даёт тот же мешок: порядок слов потерян",
           "muted small", "middle")
    f.save("bow")


# --- 3б. таблица мешков слов ------------------------------------------------
REVIEWS = [
    ("отличный фильм", 1), ("очень хороший фильм", 1),
    ("хороший сюжет и отличная музыка", 1), ("актёры играют хорошо", 1),
    ("скучный фильм", 0), ("очень плохой фильм", 0),
    ("плохой сюжет и скучная музыка", 0), ("актёры играют плохо", 0),
]


def fig_bow_matrix():
    # Как CountVectorizer по умолчанию: слова из двух и более букв, словарь по алфавиту.
    vocab = sorted({w for text, _ in REVIEWS for w in text.split() if len(w) > 1})
    f = Figure(640, 298, "Таблица мешков слов для восьми отзывов",
               "Восемь отзывов по строкам, 14 слов словаря по столбцам, в ячейках — число вхождений слова "
               "в отзыв. Справа — метка отзыва: 1 у четырёх положительных, 0 у четырёх отрицательных.")
    x0, y0, w, h = 262, 73, 23, 24
    for j, word in enumerate(vocab):
        x = x0 + j * w + w / 2 + 4
        f.items.append(f'<text x="{x:.1f}" y="{y0 - 8}" transform="rotate(-55 {x:.1f} {y0 - 8})" '
                       f'class="small">{word}</text>')
    f.text(x0 + len(vocab) * w + 26, y0 - 8, "метка", "small bold", "middle")
    for i, (text, label) in enumerate(REVIEWS):
        y = y0 + i * h
        f.text(x0 - 10, y + h / 2 + 5, text, "small", "end")
        words = text.split()
        for j, word in enumerate(vocab):
            count = words.count(word)
            f.rect(x0 + j * w, y, w, h, fill="blue-tint" if count else "none", stroke="line", rx=0, width=1)
            f.text(x0 + j * w + w / 2, y + h / 2 + 5, str(count), "small bold blue" if count else "small muted",
                   "middle")
        color = "green" if label else "orange"
        f.rect(x0 + len(vocab) * w + 12, y + 2, 28, h - 4, fill=f"{color}-tint", stroke="none", rx=4)
        f.text(x0 + len(vocab) * w + 26, y + h / 2 + 5, str(label), f"small bold {color}", "middle")
    yb = y0 + len(REVIEWS) * h + 22
    f.text(x0 + len(vocab) * w / 2, yb, "признаки: по столбцу на каждое слово словаря", "muted small", "middle")
    f.text(x0 - 10, yb, "объекты: по строке на отзыв", "muted small", "end")
    f.save("bow-matrix")


# --- 4. выбор строки таблицы -----------------------------------------------
def fig_lookup():
    words = ["кот", "собака", "ракета", "самолёт"]
    E = [[0.9, 0.1], [0.8, 0.2], [0.1, 0.9], [0.2, 0.8]]
    f = Figure(640, 210, "Эмбеддинг как строка таблицы",
               "Слово «собака» имеет индекс 1. По этому номеру из таблицы эмбеддингов размера 4 на 2 "
               "берётся строка 1, (0,8; 0,2).")
    w, h = 54, 36
    ex, ey = 300, 30

    def row_y(i):
        return ey + i * (h + 6)

    f.cell(20, row_y(1), "собака", w=84, h=h, fill="blue-tint", stroke="blue", cls="bold")
    f.text(62, row_y(1) - 10, "слово", "muted small", "middle")
    f.line(110, row_y(1) + h / 2, 150, row_y(1) + h / 2, color="axis", arrow=True)
    f.cell(156, row_y(1), "1", w=44, h=h, fill="blue-tint", stroke="blue", cls="bold blue")
    f.text(178, row_y(1) - 10, "индекс", "muted small", "middle")
    f.line(206, row_y(1) + h / 2, ex - 40, row_y(1) + h / 2, color="blue", arrow=True)
    f.text(ex + w, 20, "таблица E (4 × 2)", "muted small", "middle")
    for i, (row, word) in enumerate(zip(E, words)):
        y = row_y(i)
        hot = i == 1
        f.text(ex - 12, y + h / 2 + 5, str(i), "bold blue" if hot else "muted", "end")
        for k, v in enumerate(row):
            f.cell(ex + k * w + 2, y, num(v), w=w - 4, h=h, fill="orange-tint" if hot else "none",
                   stroke="orange" if hot else "line", cls="bold" if hot else "")
        f.text(ex + 2 * w + 8, y + h / 2 + 5, word, "orange small" if hot else "muted small")
    f.line(ex + 2 * w + 64, row_y(1) + h / 2, ex + 2 * w + 100, row_y(1) + h / 2, color="axis", arrow=True)
    for k, v in enumerate(E[1]):
        f.cell(ex + 2 * w + 106 + k * w, row_y(1), num(v), w=w - 4, h=h, fill="orange-tint", stroke="orange",
               cls="bold")
    f.text(ex + 2 * w + 106 + w, row_y(1) - 10, "эмбеддинг", "muted small", "middle")
    f.save("lookup")


# --- 5. окно контекста ----------------------------------------------------
def fig_window():
    sentence = ["кот", "пьёт", "молоко"]
    f = Figure(640, 150, "Окно контекста ширины 2",
               "Окно проходит по предложению «кот пьёт молоко». Для каждого центрального слова выделены "
               "два соседа и записаны пары: кот–пьёт, кот–молоко, пьёт–кот, пьёт–молоко, молоко–кот, молоко–пьёт.")
    pw = 213
    for c in range(3):
        x0 = c * pw + 8
        f.text(x0 + 101, 20, f"центр: «{sentence[c]}»", "blue small", "middle")
        for i, word in enumerate(sentence):
            center = i == c
            f.cell(x0 + i * 68, 32, word, w=66, h=34, fill="blue-tint" if center else "orange-tint",
                   stroke="blue" if center else "orange", cls="bold" if center else "")
        pairs = [f"({sentence[c]}, {w})" for i, w in enumerate(sentence) if i != c]
        for k, p in enumerate(pairs):
            f.text(x0 + 101, 96 + 20 * k, p, "muted small", "middle")
    f.save("window")


# --- 5б. таблица соседей ------------------------------------------------
def fig_cooc():
    sentences = [line.split() for line in TEXT.splitlines()]
    rows = ["кот", "собака", "ракета", "самолёт"]
    cols = ["пьёт", "молоко", "воду", "ловит", "мышь", "мяч", "спит", "дома",
            "летит", "высоко", "несёт", "спутник", "пассажиров"]
    counts = {(r, c): 0 for r in rows for c in cols}
    for s in sentences:
        for i, a in enumerate(s):
            for j, b in enumerate(s):
                if i != j and (a, b) in counts:
                    counts[a, b] += 1
    common = [c for c in cols if counts["кот", c] and counts["собака", c]]
    f = Figure(640, 247, "Строки таблицы соседей",
               "Строки таблицы соседей для слов «кот», «собака», «ракета», «самолёт». Столбцы пьёт, ловит, спит, "
               "дома, общие для кота и собаки, выделены. У «ракеты» и «самолёта» общие столбцы летит, высоко, несёт.")
    x0, y0, w, h = 92, 85, 36, 30
    for j, c in enumerate(cols):
        x = x0 + j * w + w / 2 + 4
        cls = "small bold green" if c in common else "small"
        f.items.append(f'<text x="{x:.1f}" y="{y0 - 8}" transform="rotate(-55 {x:.1f} {y0 - 8})" '
                       f'class="{cls}">{c}</text>')
    for j, c in enumerate(cols):
        if c in common:  # общие соседи кота и собаки: рамка на две строки
            f.rect(x0 + j * w + 1, y0 + 1, w - 2, 2 * h - 2, fill="green-tint", stroke="none", rx=3)
    for i, r in enumerate(rows):
        y = y0 + i * h + (8 if i >= 2 else 0)
        color = "orange" if i < 2 else "blue"
        f.text(x0 - 10, y + h / 2 + 5, r, "bold", "end")
        for j, c in enumerate(cols):
            v = counts[r, c]
            f.rect(x0 + j * w, y, w, h, fill="none", stroke="line", rx=0, width=1)
            f.text(x0 + j * w + w / 2, y + h / 2 + 5, str(v), f"bold {color}" if v else "muted small", "middle")
        f.text(x0 + len(cols) * w + 12, y + h / 2 + 5, f"{sum(counts[r, c] for c in cols)} соседей", "muted small")
    yb = y0 + 4 * h + 30
    f.text(x0, yb, "общих соседей у «кота» и «собаки»: 4 из 6", "green small bold")
    f.save("cooc")


# --- 6. word2vec ----------------------------------------------------------
def train_word2vec():
    from gensim.models import Word2Vec

    sentences = [line.split() for line in TEXT.splitlines()]
    return Word2Vec(sentences, vector_size=10, window=2, min_count=1, sg=1, sample=0,
                    epochs=1000, seed=0, workers=1)


def fig_skipgram(model):
    p = dict(model.predict_output_word(["кот"], topn=len(model.wv)))
    shown = ["пьёт", "спит", "ловит", "мышь", "молоко", "дома", "летит", "ракета"]
    neighbours = {"пьёт", "спит", "ловит", "мышь", "молоко", "дома"}
    f = Figure(640, 250, "Как word2vec угадывает соседей",
               "Слово «кот» превращается в вектор из 10 чисел, вектор подаётся в нейросеть, она выдаёт "
               "вероятности соседей. После обучения шесть настоящих соседей кота получают вероятности "
               "от 0,09 до 0,2, а «летит» и «ракета» — почти ноль.")
    yc = 135
    f.cell(8, yc - 18, "кот", w=56, h=36, fill="blue-tint", stroke="blue", cls="bold")
    f.text(36, yc + 40, "слово", "muted small", "middle")
    f.line(68, yc, 92, yc, color="axis", arrow=True)
    for k in range(10):
        f.rect(96 + k * 11, yc - 18, 11, 36, fill="orange-tint", stroke="orange", rx=0, width=1)
    f.text(151, yc + 40, "вектор: 10 чисел", "muted small", "middle")
    f.line(210, yc, 234, yc, color="axis", arrow=True)
    f.rect(238, yc - 34, 132, 68, fill="none", stroke="line", rx=10)
    f.text(304, yc - 4, "нейросеть", "small bold", "middle")
    f.text(304, yc + 16, "угадывает соседа", "muted small", "middle")
    f.line(374, yc, 398, yc, color="axis", arrow=True)
    f.text(510, 18, "вероятность соседа", "muted small", "middle")
    bx, scale = 470, 600
    for i, word in enumerate(shown):
        y = 28 + i * 27
        true = word in neighbours
        color = "green" if true else "muted"
        f.text(bx - 6, y + 15, word, ("bold " if true else "") + "small", "end")
        value = float(p.get(word, 0.0))
        f.rect(bx, y + 4, max(2.0, value * scale), 15, fill=color, stroke="none", rx=3)
        f.text(bx + max(2.0, value * scale) + 5, y + 16, num(value), "muted small")
    f.save("skipgram")


# --- 7. карта слов GloVe ------------------------------------------------
# Английские слова из выборки GloVe и их переводы для подписей.
TOPICS = {
    "животные": {"dog": "собака", "cat": "кошка", "horse": "лошадь", "cow": "корова", "pig": "свинья",
                 "bird": "птица"},
    "еда": {"pizza": "пицца", "bread": "хлеб", "cheese": "сыр", "chocolate": "шоколад", "coffee": "кофе",
            "cake": "торт"},
    "страны": {"france": "Франция", "germany": "Германия", "italy": "Италия", "spain": "Испания",
               "japan": "Япония", "china": "Китай"},
    "цвета": {"red": "красный", "blue": "синий", "green": "зелёный", "yellow": "жёлтый", "black": "чёрный",
              "white": "белый"},
    "числа": {"one": "один", "two": "два", "three": "три", "four": "четыре", "five": "пять", "six": "шесть"},
    "спорт": {"football": "футбол", "basketball": "баскетбол", "tennis": "теннис", "hockey": "хоккей",
              "golf": "гольф", "baseball": "бейсбол"},
}
TOPIC_COLORS = ["orange", "green", "blue", "red", "yellow", "purple"]


def fig_wordmap():
    from sklearn.manifold import TSNE

    data = np.load(HERE / "data" / "glove-twitter.npz")
    index = {word: i for i, word in enumerate(data["words"].tolist())}
    vectors = data["vectors"].astype(np.float32)
    words = [w for ws in TOPICS.values() for w in ws]
    labels = [ru for ws in TOPICS.values() for ru in ws.values()]
    topics = [k for k, ws in enumerate(TOPICS.values()) for _ in ws]
    # t-SNE переносит 100-мерные векторы на плоскость, стараясь сохранить, кто кому сосед.
    P = TSNE(2, perplexity=8, random_state=0, init="pca", metric="cosine").fit_transform(
        vectors[[index[w] for w in words]])
    f = Figure(640, 500, "Карта слов GloVe",
               "Векторы 36 английских слов из шести тем перенесены на плоскость и подписаны переводами. "
               "Слова одной темы собираются в облака: животные, еда, страны, цвета, числа, спорт.")
    lo, hi = P.min(axis=0), P.max(axis=0)
    left, top, width, height = 70, 40, 360, 400
    pts = [(left + (p[0] - lo[0]) / (hi[0] - lo[0]) * width, top + (hi[1] - p[1]) / (hi[1] - lo[1]) * height)
           for p in P]
    # Подписи раскладываем жадно: пробуем места вокруг точки по возрастанию расстояния
    # и берём первое, которое не задевает уже поставленные подписи и точки.
    boxes = []

    def free(box):
        x0, y0, x1, y1 = box
        if x0 < 50 or x1 > 520 or y0 < 14 or y1 > 456:
            return False
        if any(not (x1 < a0 or x0 > a1 or y1 < b0 or y0 > b1) for a0, b0, a1, b1 in boxes):
            return False
        return not any(x0 - 3 < px < x1 + 3 and y0 - 3 < py < y1 + 3 for px, py in pts)

    # Сетка и оси: левая и нижняя границы карты.
    ax0, ay0, ax1, ay1 = 44, 466, 528, 16
    for gx in range(int(ax0) + 60, int(ax1), 60):
        f.line(gx, ay0, gx, ay1 + 8, color="grid", width=1)
    for gy in range(int(ay0) - 60, int(ay1), -60):
        f.line(ax0, gy, ax1 - 8, gy, color="grid", width=1)
    f.line(ax0, ay0, ax1, ay0, color="axis", width=1.5, arrow=True)
    f.line(ax0, ay0, ax0, ay1, color="axis", width=1.5, arrow=True)
    f.text(ax1, ay0 + 22, "ось 1", "muted small", "end")
    f.items.append(f'<text x="{ax0 - 10}" y="{ay1 + 4}" text-anchor="end" class="muted small" '
                   f'transform="rotate(-90 {ax0 - 10} {ay1 + 4})">ось 2</text>')
    order = sorted(range(len(words)), key=lambda i: pts[i][1])
    for i in order:
        x, y = pts[i]
        w, h = 7.2 * len(labels[i]) + 2, 14
        placed = None
        for r in range(6, 90, 4):
            for ang in range(0, 360, 30):
                dx, dy = r * np.cos(np.radians(ang)), -r * np.sin(np.radians(ang))
                bx = x + dx if dx >= 0 else x + dx - w
                by = y + dy - h / 2
                if free((bx, by, bx + w, by + h)):
                    placed = (bx, by, dx, dy)
                    break
            if placed:
                break
        bx, by, dx, dy = placed
        boxes.append((bx, by, bx + w, by + h))
        color = TOPIC_COLORS[topics[i]]
        if np.hypot(dx, dy) > 12:
            f.line(x, y, bx if dx >= 0 else bx + w, by + h / 2, color=color, width=0.7, opacity=0.6)
        f.text(bx, by + h - 3, labels[i], f"small {color}")
    for (x, y), k in zip(pts, topics):
        f.circle(x, y, 4, TOPIC_COLORS[k])
    for k, name in enumerate(TOPICS):
        f.circle(538, 60 + k * 26, 5, TOPIC_COLORS[k])
        f.text(550, 65 + k * 26, name, f"bold {TOPIC_COLORS[k]}")
    f.save("wordmap")


if __name__ == "__main__":
    MEDIA.mkdir(exist_ok=True)
    fig_onehot()
    fig_compare()
    fig_bow()
    fig_bow_matrix()
    fig_lookup()
    fig_window()
    fig_cooc()
    fig_skipgram(train_word2vec())
    fig_wordmap()
