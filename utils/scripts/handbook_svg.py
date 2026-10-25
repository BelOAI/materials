"""Векторный PDF из SVG с печатными CSS, переменными и узорами Chromium."""
from __future__ import annotations

import hashlib
import importlib.metadata
from pathlib import Path
from xml.etree import ElementTree

ElementTree.register_namespace('', 'http://www.w3.org/2000/svg')
ElementTree.register_namespace('xlink', 'http://www.w3.org/1999/xlink')


INSTALL = 'python3 -m playwright install chromium --no-shell'


def renderer_identity():
    """Версия движка для кэша без запуска самого браузера."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as error:
        raise ValueError('Установите зависимости utils/pdf/requirements.txt и выполните ' + INSTALL) from error
    with sync_playwright() as playwright:
        executable = Path(playwright.chromium.executable_path)
    if not executable.is_file():
        raise ValueError('Не установлен Chromium для PDF: ' + INSTALL)
    return (importlib.metadata.version('playwright'), hashlib.sha256(executable.read_bytes()).hexdigest())


def render_svg(source: Path, destination: Path):
    """Печатать SVG в DOM: без скриптов, сети и растрирования схемы."""
    try:
        root = ElementTree.fromstring(source.read_bytes())
    except ElementTree.ParseError as error:
        raise ValueError(f'Неверный SVG {source}: {error}') from error
    if root.tag != '{http://www.w3.org/2000/svg}svg':
        raise ValueError(f'Не найден корневой SVG: {source}')
    from playwright.sync_api import sync_playwright, Error

    # SVG в DOM наследует print media страницы; у <img> остаётся собственная screen media.
    fragment = ElementTree.tostring(root, encoding='unicode')
    html = ('<!doctype html><html><head><style>'
            'html,body{margin:0;padding:0}body>svg{position:absolute;left:0;top:0;display:block;'
            '-webkit-print-color-adjust:exact;print-color-adjust:exact}'
            '</style></head><body>' + fragment + '</body></html>')
    try:
        with sync_playwright() as playwright:
            # Именно этот бинарник учитывается в renderer_identity, без отдельного headless shell.
            browser = playwright.chromium.launch(channel='chromium', headless=True)
            try:
                context = browser.new_context(java_script_enabled=False)
                context.route('**/*', lambda route: route.abort())
                page = context.new_page()
                page.emulate_media(media='print', color_scheme='light')
                page.set_content(html)
                dimensions = page.locator('body > svg').evaluate('''svg => {
                    const box = svg.getBoundingClientRect();
                    return [box.width, box.height];
                }''')
                width, height = dimensions
                if width <= 0 or height <= 0:
                    raise ValueError(f'Неверные размеры SVG: {source}')
                page.pdf(path=str(destination), width=f'{width}px', height=f'{height}px',
                         margin={side: '0' for side in ('top', 'right', 'bottom', 'left')},
                         print_background=True)
            finally:
                browser.close()
    except Error as error:
        raise ValueError(f'Не удалось преобразовать SVG {source}: {error}') from error
