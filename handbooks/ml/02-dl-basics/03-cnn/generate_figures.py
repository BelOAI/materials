"""Воспроизводимые SVG-иллюстрации 1–7: Python 3, без внешних библиотек."""

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

from pathlib import Path
from xml.sax.saxutils import escape
import argparse


class Drawing:
    def __init__(self, height, title, description):
        self.height = height
        self.parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="560" height="{height}" viewBox="0 0 560 {height}" role="img" aria-labelledby="title desc">',
                      f'<title id="title">{escape(title)}</title>',
                      f'<desc id="desc">{escape(description)}</desc>',
                      '<style id="handbook-style"></style>',
                      f'<style>.value {{font-size:{SIZES["heading"]}px}} .caption {{font-size:{SIZES["body"]}px}}</style>']

    def text(self, x, y, label, cls='', fill='ink', anchor='middle'):
        self.parts.append(f'<text x="{x}" y="{y}" text-anchor="{anchor}" class="{cls}" fill="var(--{fill})">{escape(str(label))}</text>')

    def rect(self, x, y, w, h, fill='blue-bg', stroke='edge', sw=1):
        self.parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="var(--{fill})" stroke="var(--{stroke})" stroke-width="{sw}"/>')

    def arrow(self, x1, y1, x2, y2):
        self.parts.append(f'<path d="M{x1} {y1}L{x2} {y2}" class="flow"/>')

    def grid(self, values, x, y, cell, kind='input', large=False):
        for row, line in enumerate(values):
            for col, value in enumerate(line):
                if kind in ('red', 'green', 'blue'):
                    fill = kind if value == 1 else kind+'-bg' if value == .5 else 'paper'
                    ink = 'paper' if value == 1 else 'ink'
                elif kind == 'kernel':
                    fill = 'orange' if value < 0 else 'purple' if value > 0 else 'blue-bg'
                    ink = 'paper' if value else 'ink'
                elif kind == 'map':
                    fill = 'purple' if value > 0 else 'orange' if value < 0 else 'blue-bg'
                    ink = 'paper' if value else 'ink'
                else:
                    fill = 'orange' if value else 'blue-bg'
                    ink = 'paper' if value else 'ink'
                xx, yy = x+col*cell, y+row*cell
                self.rect(xx, yy, cell, cell, fill)
                label = str(value).replace('.', ',').replace('-', '−')
                self.text(xx+cell/2, yy+cell/2+(10 if large else 7), label,
                          'big' if large else 'value', ink)

    def frame(self, x, y, width, height):
        self.parts.append(f'<rect x="{x}" y="{y}" width="{width}" height="{height}" fill="none" stroke="var(--purple)" stroke-width="3"/>')

    def save(self, folder, name):
        (folder/(name+'.svg')).write_text(normalize_svg(''.join(self.parts)+'</svg>'), encoding='utf-8')


def make_figures(folder):
    folder.mkdir(parents=True, exist_ok=True)
    rgb = [[(0,.5,1)]*4,
           [(0,.5,1),(1,0,.5),(1,0,.5),(0,.5,1)],
           [(0,.5,1),(1,.5,0),(1,.5,0),(0,.5,1)],
           [(0,1,.5)]*4]
    d = Drawing(574, 'Изображение и его цветовые каналы',
                'Цветной домик и таблицы R, G, B. Для стены значения равны 1, 0,5 и 0. Панели расположены в два ряда.')
    panels = [(50,66,'Изображение'),(334,66,'Красный R'),(50,352,'Зелёный G'),(334,352,'Синий B')]
    for index, (x,y,title) in enumerate(panels):
        d.text(x+88,y-22,title,'heading','blue')
        if index == 0:
            for row,line in enumerate(rgb):
                for col,value in enumerate(line):
                    fill='rgb('+','.join(str(round(255*c)) for c in value)+')'
                    d.parts.append(f'<rect x="{x+col*44}" y="{y+row*44}" width="44" height="44" fill="{fill}" stroke="var(--edge)"/>')
        else:
            channel=index-1
            d.grid([[value[channel] for value in row] for row in rgb],x,y,44,['red','green','blue'][channel])
    d.save(folder,'pixels')

    a=[[0]*7 for _ in range(6)]
    for i in range(1,4):a[i][1]=1
    for j in range(1,4):a[3][j]=1
    b=[[0,0]+row[:-2] for row in a]
    d=Drawing(264,'Поиск одной детали в разных частях изображения',
              'Один уголок слева и его копия, сдвинутая на две клетки вправо. Рамки выделяют одинаковые участки 3 на 3.')
    for x,values,title,start in [(30,a,'Угол слева',1),(320,b,'Тот же угол справа',3)]:
        d.text(x+105,32,title,'heading','blue');d.grid(values,x,58,30);d.frame(x+start*30,88,90,90)
    d.save(folder,'shift')

    image=[[0,0,1,1] for _ in range(4)]
    kv=[[-1,1],[-1,1]];kh=[[-1,-1],[1,1]]
    vertical=[[0,2,0] for _ in range(3)];horizontal=[[0]*3 for _ in range(3)]
    d=Drawing(242,'Три положения одного фильтра',
              'Окно 2 на 2 проходит по верхней строке изображения 4 на 4. Последовательные отклики равны 0, 2 и 0.')
    for i,x in enumerate([24,204,384]):
        d.text(x+64,31,f'Положение {i+1}','heading','blue');d.grid(image,x,57,32);d.frame(x+i*32,57,64,64)
        d.text(x+64,220,f'Отклик: {[0,2,0][i]}','value')
    d.save(folder,'convolution')

    d=Drawing(490,'Вычисление отклика фильтра',
              'Окно 0,1;0,1 умножается по клеткам на веса −1,1;−1,1. Произведения 0,1;0,1 складываются: 0+1+0+1=2.')
    d.text(126,34,'Окно изображения','heading','blue');d.text(426,34,'Веса фильтра','heading','blue')
    patch=[[0,1],[0,1]];d.grid(patch,70,65,56);d.grid(kv,370,65,56,'kernel');d.text(280,135,'×','big','blue')
    d.text(280,233,'Умножаем по клеткам','heading')
    d.text(126,288,'Произведения','heading','blue');d.grid(patch,70,312,56)
    d.text(282,316,'Складываем','caption');d.arrow(220,368,338,368)
    d.text(430,353,'0 + 1 + 0 + 1','value');d.text(430,411,'= 2','big','blue')
    d.save(folder,'arithmetic')

    d=Drawing(280,'Карта откликов на вертикальную границу',
              'Три строки карты: 0,2,0. Положительные отклики отмечают вертикальную границу.')
    d.grid(vertical,178,30,68,'map',large=True);d.save(folder,'boundary-map')

    d=Drawing(526,'Два фильтра на одном изображении',
              'Два ряда. В каждом изображение 4 на 4, фильтр 2 на 2 и карта 3 на 3. Фильтр А даёт строки 0,2,0, фильтр Б — нули.')
    for row,(kernel,result,letter) in enumerate([(kv,vertical,'А'),(kh,horizontal,'Б')]):
        y=row*274
        if row==0:d.text(96,32,'Изображение','heading','blue')
        else:
            d.text(96,y+12,'То же','heading','blue');d.text(96,y+38,'изображение','heading','blue')
        d.text(280,y+32,'Фильтр '+letter,'heading','blue');d.text(474,y+32,'Карта '+letter,'heading','blue')
        d.grid(image,24,y+66,36);d.grid(kernel,232,y+90,48,'kernel');d.grid(result,408,y+72,44,'map')
        d.arrow(182,y+138,214,y+138);d.arrow(348,y+138,388,y+138)
    d.save(folder,'featuremaps')

    d=Drawing(766,'Дополнение нулями и шаг фильтра',
              'Изображение 5 на 5 и окно 3 на 3: без рамки, шаг 1, карта 3 на 3; с рамкой нулей, шаг 1, карта 5 на 5; без рамки, шаг 2, карта 2 на 2.')
    for y,pad,stride,nout in [(0,False,1,3),(236,True,1,5),(528,False,2,2)]:
        d.text(280,y+30,'Рамка из нулей: шаг 1' if pad else f'Без дополнения: шаг {stride}','heading')
        n=7 if pad else 5;x=136-n*11;top=y+54
        for r in range(n):
            for c in range(n):
                rim=pad and (r in (0,n-1) or c in (0,n-1));d.rect(x+c*22,top+r*22,22,22,'orange-bg' if rim else 'blue-bg')
                if rim:d.text(x+c*22+11,top+r*22+18,'0','value','orange')
        d.frame(x,top,66,66)
        ox=410-nout*13;oy=y+90
        for r in range(nout):
            for c in range(nout):d.rect(ox+c*26,oy+r*26,26,26,'purple' if (r,c)==(0,0) else 'purple-bg')
        d.arrow(250,y+116,316,y+116);d.text(280,y+176,'Окно 3 × 3','caption')
        label_y=y+(236 if pad else 214)
        d.text(136,label_y,'Изображение 5 × 5','caption');d.text(410,label_y,f'Карта {nout} × {nout}','caption')
        if pad:d.text(136,label_y+26,'с рамкой из нулей','caption')
    d.save(folder,'paddingstride')


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description='Создать собственные SVG-рисунки 1–7 параграфа о CNN. Рисунок 8 редактируется отдельно.')
    parser.add_argument('--output-dir',type=Path,default=Path(__file__).resolve().parent/'media')
    make_figures(parser.parse_args().output_dir)
