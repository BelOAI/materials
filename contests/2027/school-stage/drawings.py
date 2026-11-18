"""Создаёт SVG к условиям школьного этапа."""
from html import escape
from pathlib import Path
import sys

BASE = Path(__file__).parent
sys.path.insert(0, str(BASE.parents[2] / "utils/illustrations"))
from style import normalize_svg

CUSTOM_STYLE = """<style>
.cell { fill:var(--paper); stroke:var(--edge); stroke-width:1.4 }
.marked { fill:var(--blue-bg); stroke:var(--blue); stroke-width:1.5 }
.bad { fill:var(--orange-bg); stroke:var(--orange); stroke-width:1.5 }
.edge { fill:none; stroke:var(--axis); stroke-width:1.5 }
.lineblue { fill:none; stroke:var(--blue); stroke-width:2.5 }
.lineorange { fill:none; stroke:var(--orange); stroke-width:2.5 }
</style>"""


def svg(name, width, height, title, description, body):
    path = BASE / name / "media" / "statement.svg"
    path.parent.mkdir(parents=True, exist_ok=True)
    source = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
              f'viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">'
              f'<title id="title">{escape(title)}</title><desc id="desc">{escape(description)}</desc>'
              f'{CUSTOM_STYLE}{body}</svg>')
    path.write_text(normalize_svg(source), encoding="utf-8")


def label(x, y, value, css="small", anchor="middle"):
    return f'<text x="{x}" y="{y}" text-anchor="{anchor}" class="{css}">{escape(str(value))}</text>'


def box(x, y, w, h, css="cell"):
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="3" class="{css}"/>'


def dot(x, y, css="blue"):
    return f'<circle cx="{x}" cy="{y}" r="4" class="{css}"/>'


def matrix(values, forbidden=()):
    items = []
    for i in range(4):
        items += [label(15, 45+i*31, i+1), label(42+i*31, 19, i+1)]
        for j in range(4):
            key = (i, j)
            value = values.get(key, "×" if key in forbidden else "?")
            css = "bad" if key in forbidden else "marked" if value == "1" else "cell"
            x, y = 28+j*31, 25+i*31
            items += [box(x, y, 28, 28, css), label(x+14, y+20, value)]
    return "".join(items)


pixels = "".join(box(10+16*j, 6+16*i, 15, 15, "marked" if (i, j)==(1, 2) else "cell")
                 for i in range(4) for j in range(5))
svg("image-size", 330, 100, "Схема хранения пикселей",
    "Сетка имеет размер 1024 × 1024 пикселя. Один пиксель занимает четыре байта.",
    pixels + label(50, 90, "1024 × 1024")
    + '<path d="M103 38H137" class="flow"/>'
    + label(233, 22, "Один пиксель")
    + "".join(box(157+39*i, 31, 35, 31, "marked") + label(174.5+39*i, 53, i+1)
              for i in range(4))
    + label(233, 86, "4 байта"))

svg("last-one", 157, 153, "Известные и неизвестные клетки",
    "Единицы стоят в клетках (1, 2), (2, 4) и (4, 1). Остальные клетки обозначены вопросительными знаками.",
    matrix({(0, 1): "1", (1, 3): "1", (3, 0): "1"}))

purchases = ("XAB", "XA", "XBC", "XAC", "XB", "C", "XAD", "XC", "BD", "XAB")
items = [label(47+j*48, 19, product) for j, product in enumerate("XABCD")]
for i, cart in enumerate(purchases):
    y = 25+i*17
    items.append(label(15, y+13, i+1))
    for j, product in enumerate("XABCD"):
        x = 26+j*48
        items.append(box(x, y, 42, 15, "marked" if product in cart else "cell"))
        if product in cart:
            items.append(f'<circle cx="{x+21}" cy="{y+7.5}" r="4" class="blue"/>')
description = "Покупки по строкам: " + "; ".join(
    f"{i} — {', '.join(cart)}" for i, cart in enumerate(purchases, 1)
) + "."
svg("associated-product", 265, 199, "Матрица покупок", description, "".join(items))

svg("two-directions", 410, 156, "Два последовательных перемещения",
    "Из O в M ведёт вектор αu, из M в P — вектор βv. Координаты P равны (2,6; 3,9). Схема не в масштабе.",
    '<path d="M32 141V8M12 131H389" class="axis"/>'
    '<path d="M32 131L162 48" class="lineblue" marker-end="url(#handbook-arrow)"/>'
    '<path d="M162 48L288 33" class="lineorange" marker-end="url(#handbook-arrow)"/>'
    + dot(32, 131) + dot(162, 48) + dot(288, 33, "orange")
    + label(22, 150, "O") + label(157, 31, "M")
    + label(298, 39, "P (2,6; 3,9)", anchor="start")
    + label(85, 78, "αu", "blue") + label(225, 28, "βv", "orange")
    + label(393, 150, "x") + label(43, 18, "y"))

def graph_point(x, y):
    return 28 + 139*x, 90 - 26*y


curve = " ".join(f"{px:.1f},{py:.1f}" for x in (i/40 for i in range(101))
                 for px, py in [graph_point(x, 2**x - 3.4)])
left = graph_point(1, -1.4)
right = graph_point(2, 0.6)
svg("secant-axis", 400, 174, "Кривая и секущий отрезок",
    "График y = 2ˣ − 3,4. Точки при x₁ = 1 и x₂ = 2 соединены отрезком, который пересекает ось Ox.",
    '<path d="M28 163V14M15 90H390" class="axis"/>'
    f'<polyline points="{curve}" class="lineblue"/>'
    f'<path d="M{left[0]} {left[1]}L{right[0]} {right[1]}" class="lineorange"/>'
    + dot(*left, "orange") + dot(*right, "orange")
    + label(104, 36, "y = 2ˣ − 3,4", "blue")
    + label(164, 150, "x₁ = 1") + label(336, 64, "x₂ = 2")
    + label(239, 82, "x = ?", "orange") + label(386, 109, "x") + label(40, 19, "y"))

vertices = [(37, 44, "010", "10"), (159, 44, "110", "?"),
            (233, 78, "011", "?"), (355, 78, "111", "?"),
            (37, 130, "000", "7"), (159, 130, "100", "5"),
            (233, 164, "001", "6"), (355, 164, "101", "?")]
edges = "".join(f'M{x} {y}L{u} {v}' for i, (x, y, a, _) in enumerate(vertices)
                for u, v, b, _ in vertices[i+1:] if sum(c != d for c, d in zip(a, b)) == 1)
items = [f'<path d="{edges}" class="edge"/>']
for x, y, bits, value in vertices:
    css = "marked" if value != "?" else "cell"
    items.extend((box(x-27, y-20, 54, 40, css),
                  label(x, y-2, bits), label(x, y+15, "f="+value, "small m")))
svg("linear-model-minimum", 386, 190, "Вершины бинарного куба",
    "Восемь бинарных входов. Известны значения f(000)=7, f(100)=5, f(010)=10 и f(001)=6.",
    "".join(items))

nodes = [(200, 17, "x < 20"), (105, 79, "y < 30"), (295, 79, "y < 30"),
         (48, 143, "+1"), (146, 143, "+2"), (254, 143, "−1"), (352, 143, "+3")]
items = ['<path d="M200 29L105 67M200 29L295 67M105 91L48 131M105 91L146 131M295 91L254 131M295 91L352 131" class="edge"/>']
for x, y, value in nodes:
    items.extend((box(x-35, y-12, 70, 24, "marked" if y==143 else "cell"),
                  label(x, y+6, value)))
for x, y, value in [(138, 47, "да"), (262, 47, "нет"), (56, 108, "да"),
                    (149, 108, "нет"), (250, 108, "да"), (351, 108, "нет")]:
    items.append(label(x, y, value))
svg("decision-tree-sum", 400, 161, "Дерево решений",
    "Сначала проверяется x < 20, затем y < 30. Ответы в листьях слева направо: 1, 2, −1, 3.",
    "".join(items))

points = [("A", 2, 1), ("B", 7, 13), ("C", 24, 3),
          ("D", -12, 26), ("E", -8, 10), ("F", 28, -10)]
items = ['<path d="M14 151H269M95 11V209" class="axis"/>', label(264, 169, "x"), label(105, 17, "y")]
for name, x, y in points:
    px, py = 95+5*x, 151-5*y
    items.extend((dot(px, py), label(px+9, py-6, name, anchor="start")))
svg("circle-two-points", 278, 211, "Шесть точек на координатной плоскости",
    "Одинаковый масштаб по обеим осям. Точки " + ", ".join(f"{name}({x}, {y})" for name, x, y in points) + ".",
    "".join(items))

svg("permutation-matrices", 157, 153, "Запрещённые клетки матрицы",
    "В матрице четыре на четыре отмечены запрещённые клетки (1, 1) и (2, 2).",
    matrix({}, forbidden={(0, 0), (1, 1)}))
