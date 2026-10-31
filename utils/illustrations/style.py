"""Общее оформление SVG BelOAI; экспортируемый блок не требует этого модуля."""
from xml.etree import ElementTree as ET
import inspect
import re

STYLE_ID = 'handbook-style'
DEFS_ID = 'handbook-defs'
BEGIN = '# BEGIN HANDBOOK SVG STYLE'
END = '# END HANDBOOK SVG STYLE'
FONT = "'PT Sans','DejaVu Sans',Arial,sans-serif"
SIZES = dict(body=20, small=16, heading=22, grid=8, padding=16, gap=24,
             radius=6, line=2, axis=1.25, grid_line=.75)
PALETTE = {
    'ink': ('#1b2430', '#e3e8ee'), 'muted': ('#55657a', '#aab6c4'),
    'axis': ('#7a8a9c', '#8796a7'), 'grid': ('#d5dee8', '#3d4855'),
    'edge': ('#c9d4e0', '#46525f'),
    'blue': ('#2459c2', '#8cbcff'), 'blue-bg': ('#e8f0ff', '#1e2c42'),
    'purple': ('#7238c4', '#c7a9ff'), 'purple-bg': ('#f2eaff', '#2d2442'),
    'orange': ('#b05300', '#ffbd6b'), 'orange-bg': ('#fff2e3', '#3a2b1a'),
    'green': ('#188038', '#81c995'), 'green-bg': ('#e6f4ea', '#1c3326'),
    'red': ('#c53929', '#ff9a8a'), 'red-bg': ('#fce8e6', '#3a2227'),
    'yellow': ('#8a5a00', '#fdd663'), 'yellow-bg': ('#fef4ce', '#382f18'),
    'paper': ('#ffffff', '#212529'), 'panel': ('none', 'none'),
}


def stylesheet():
    def variables(mode):
        return ' '.join(f'--{name}:{colors[mode]};' for name, colors in PALETTE.items())
    return '\n'.join([
        ':root { color-scheme:light dark; --figure-scale:1; ' + variables(0) + ' }',
        '@media (prefers-color-scheme:dark) { :root { ' + variables(1) + ' } }',
        '@media print { :root { color-scheme:light; ' + variables(0) + ' } }',
        f'svg {{ fill:var(--ink); font-family:{FONT}; font-size:calc({SIZES["body"]}px * var(--figure-scale)); }}',
        f'text, tspan {{ font-family:{FONT}; }}',
        f'.s, .small {{ font-size:calc({SIZES["small"]}px * var(--figure-scale)); }}',
        f'.heading, .label {{ font-size:calc({SIZES["heading"]}px * var(--figure-scale)); font-weight:700; }}',
        '.b, .bold { font-weight:700; } .m { fill:var(--muted); } .i { font-style:italic; }',
        '.big { font-size:32px; font-weight:700; }',
        *[f'.{role} {{ fill:var(--{role}); }}' for role in ('blue', 'purple', 'orange', 'green', 'red', 'yellow')],
        f'.axis {{ fill:none; stroke:var(--axis); stroke-width:{SIZES["axis"]}; }}',
        f'.grid {{ fill:none; stroke:var(--grid); stroke-width:{SIZES["grid_line"]}; }}',
        f'.block {{ rx:{SIZES["radius"]}; stroke-width:{SIZES["line"]}; }}',
        f'.flow {{ fill:none; stroke:var(--axis); stroke-width:{SIZES["line"]}; marker-end:url(#handbook-arrow); }}',
    ]) + '\n'


CSS = stylesheet()
DEFS = f'''<defs xmlns="http://www.w3.org/2000/svg" id="{DEFS_ID}">
  <marker id="handbook-arrow" markerWidth="8" markerHeight="8" refX="7" refY="4"
          orient="auto" markerUnits="userSpaceOnUse">
    <path d="M0 0L8 4L0 8Z" fill="var(--axis)"/>
  </marker>
</defs>'''
COLOR_ROLES = {colors[0]: role for role, colors in PALETTE.items()
               if colors[0].startswith('#') and role != 'paper'}
COLOR_ROLES.update({'#000000': 'ink', '#262626': 'ink', '#2563eb': 'blue',
                    '#ea580c': 'orange', '#cbd5e1': 'grid'})


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


def standalone_block():
    """Скачиваемые генераторы получают автономную копию общего оформления."""
    constants = dict(STYLE_ID=STYLE_ID, DEFS_ID=DEFS_ID, CSS=CSS, DEFS=DEFS, COLOR_ROLES=COLOR_ROLES, SIZES=SIZES)
    return '\n'.join([BEGIN, 'from xml.etree import ElementTree as ET', 'import re',
                      *[f'{key} = {value!r}' for key, value in constants.items()], '',
                      *[inspect.getsource(fn) for fn in (normalize_svg, apply_matplotlib_style, finish_plot)], END])


def normalize_generator(source):
    pattern = re.compile(re.escape(BEGIN) + r'.*?' + re.escape(END), re.S)
    if len(pattern.findall(source)) != 1:
        raise ValueError('Нужен один отмеченный блок оформления генератора')
    return pattern.sub(lambda _: standalone_block(), source)
