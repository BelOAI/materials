"""Separate, colour-managed print package with explicit production assumptions."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import urllib.request

PROFILE_URL = 'https://registry.color.org/profile-registry/profiles/PSOuncoated_v3_FOGRA52.icc'
PROFILE_SHA256 = '7c39f74fbede1e8c85f8fbb9df7d359aea638b9b68dd0854fdd3ba386e3a02c0'
PROFILE_NAME = 'PSOuncoated_v3_FOGRA52.icc'
PROFILE_SOURCE = 'https://registry.color.org/profile-registry/PSOuncoated_v3_FOGRA52'
# The original terms accompany the embedded profile. Do not distribute its bare bytes.
PROFILE_LICENSE = ('Copyright Heidelberger Druckmaschinen AG. This profile is made available by ECI European Color Initiative, '
                   'with permission of Heidelberger Druckmaschinen AG, and may be used, embedded and exchanged without restriction. '
                   'It may not be distributed, sold or altered without written permission of ECI European Color Initiative. '
                   'Color Toolbox 17.0.0 - (c) Copyright 2015 Heidelberger Druckmaschinen AG. All Rights Reserved.')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def teaching_hashes(root):
    base = root / 'handbooks'
    return {p.relative_to(root).as_posix(): sha(p) for p in sorted(base.rglob('*'))
            if p.is_file() and not any(part.startswith('.') for part in p.relative_to(base).parts)}


def acquire_profile(root):
    path = root / '.cache/press-profiles' / PROFILE_NAME
    if path.is_file() and sha(path) == PROFILE_SHA256:
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(PROFILE_URL, headers={'User-Agent': 'Mozilla/5.0 BelOAI-handbook-build'})
    with urllib.request.urlopen(request, timeout=60) as response:
        data = response.read()
    if hashlib.sha256(data).hexdigest() != PROFILE_SHA256:
        raise ValueError('Изменился SHA256 официального ICC-профиля; требуется проверка источника')
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as temp:
        temp.write(data)
        temporary = Path(temp.name)
    os.replace(temporary, path)
    return path


def _text(path):
    import pymupdf
    with pymupdf.open(path) as doc:
        text = ''.join(page.get_text() for page in doc)
        # PDF producers may map the same printed ligature to fi or U+FB01.
        # Expand only typographic ligatures; retain mathematical distinctions.
        for glyph, letters in zip('ﬀﬁﬂﬃﬄﬅﬆ', ('ff', 'fi', 'fl', 'ffi', 'ffl', 'st', 'st')):
            text = text.replace(glyph, letters)
        return re.sub(r'\s+', '', text)


def prepare_document(source, destination):
    """Strip annotations without changing visible text; make a duplex interior."""
    from pypdf import PdfReader, PdfWriter
    from pypdf.generic import NameObject, RectangleObject
    reader = PdfReader(source)
    writer = PdfWriter(clone_from=reader)
    for key in ('/OpenAction', '/AA', '/AcroForm'):
        writer.root_object.pop(NameObject(key), None)
    for page in writer.pages:
        page.pop(NameObject('/Annots'), None)
        page.pop(NameObject('/AA'), None)
        page.pop(NameObject('/ArtBox'), None)
        page.trimbox = RectangleObject(page.mediabox)
        page.bleedbox = RectangleObject(page.mediabox)
    if len(writer.pages) % 2:
        box = writer.pages[0].mediabox
        writer.add_blank_page(width=box.width, height=box.height)
    writer.write(destination)


def finish_document(source, destination, profile):
    from pypdf import PdfReader, PdfWriter
    from pypdf.generic import NameObject, DictionaryObject, DecodedStreamObject, NumberObject, TextStringObject, ArrayObject, RectangleObject
    writer = PdfWriter(clone_from=PdfReader(source))
    writer.pdf_header = '%PDF-1.6'
    stream = DecodedStreamObject()
    stream.set_data(profile.read_bytes())
    stream[NameObject('/N')] = NumberObject(4)
    intent = DictionaryObject({NameObject('/Type'): NameObject('/OutputIntent'),
                              NameObject('/S'): NameObject('/GTS_PDFX'),
                              NameObject('/OutputConditionIdentifier'): TextStringObject('FOGRA52'),
                              NameObject('/RegistryName'): TextStringObject('http://www.color.org'),
                              NameObject('/Info'): TextStringObject('PSO Uncoated v3; assumed uncoated stock'),
                              NameObject('/DestOutputProfile'): writer._add_object(stream)})
    writer.root_object[NameObject('/OutputIntents')] = ArrayObject([writer._add_object(intent)])
    # Output intent is a colour-management declaration, not a PDF/X claim.
    for key in ('/GTS_PDFXVersion', '/GTS_PDFXConformance'):
        if writer.metadata:
            writer._info.get_object().pop(NameObject(key), None)
    for page in writer.pages:
        page.pop(NameObject('/Annots'), None)
        page.pop(NameObject('/ArtBox'), None)
        page.trimbox = RectangleObject(page.mediabox)
        page.bleedbox = RectangleObject(page.mediabox)
    writer.write(destination)


def preflight(path, expected_profile_sha=PROFILE_SHA256):
    import pymupdf
    from pypdf import PdfReader
    from pypdf.generic import ContentStream
    reader = PdfReader(path)
    errors, warnings = [], []
    if reader.pdf_header != '%PDF-1.6':
        errors.append('Печатный мастер должен быть PDF 1.6')
    if reader.is_encrypted:
        errors.append('PDF зашифрован')
    if len(reader.pages) % 2:
        errors.append('Нечётное число страниц')
    intents = reader.trailer['/Root'].get('/OutputIntents', [])
    if len(intents) != 1:
        errors.append('Не найден единственный OutputIntent')
    else:
        intent = intents[0].get_object()
        profile = intent.get('/DestOutputProfile')
        if not profile or profile.get_object().get('/N') != 4 or hashlib.sha256(profile.get_object().get_data()).hexdigest() != expected_profile_sha:
            errors.append('ICC-профиль не совпадает с закреплённым FOGRA52')
        if intent.get('/OutputConditionIdentifier') != 'FOGRA52':
            errors.append('Неверный OutputConditionIdentifier')
    root = reader.trailer['/Root']
    if any(key in root for key in ('/OpenAction', '/AA', '/AcroForm')):
        errors.append('Активные действия или формы в каталоге PDF')
    names = root.get('/Names', {})
    names = names.get_object() if hasattr(names, 'get_object') else names
    if any(key in names for key in ('/JavaScript', '/EmbeddedFiles')):
        errors.append('JavaScript или вложенные файлы в PDF')
    bad_spaces = set()
    seen_forms = set()
    def inspect(stream, resources):
        # Inspect content operators and nested forms; accept Gray and process CMYK.
        resources = resources.get_object() if hasattr(resources, 'get_object') else resources
        spaces = resources.get('/ColorSpace', {})
        spaces = spaces.get_object() if hasattr(spaces, 'get_object') else spaces
        xobjects = resources.get('/XObject', {})
        xobjects = xobjects.get_object() if hasattr(xobjects, 'get_object') else xobjects
        for args, op in ContentStream(stream, reader).operations:
            if op in (b'rg', b'RG'):
                bad_spaces.add('DeviceRGB')
            if op in (b'cs', b'CS') and args:
                space = spaces.get(args[0], args[0])
                value = space.get_object() if hasattr(space, 'get_object') else space
                if str(value) in ('/DeviceRGB', '/CalRGB', '/Lab'):
                    bad_spaces.add(str(value))
                if isinstance(value, list) and value:
                    if str(value[0]) in ('/CalRGB', '/Lab'):
                        bad_spaces.add(str(value[0]))
                    elif str(value[0]) == '/ICCBased' and value[1].get_object().get('/N') == 3:
                        bad_spaces.add('ICCBased RGB')
            if op == b'Do':
                ref = xobjects.get(args[0])
                if not ref:
                    continue
                obj = ref.get_object()
                if obj.get('/Subtype') == '/Form' and ref.idnum not in seen_forms:
                    seen_forms.add(ref.idnum)
                    inspect(obj, obj.get('/Resources', resources))
                if obj.get('/Subtype') == '/Image':
                    space = obj.get('/ColorSpace')
                    if str(space) == '/DeviceRGB' or (isinstance(space, list) and str(space[0]) == '/ICCBased' and space[1].get_object().get('/N') == 3):
                        bad_spaces.add('RGB image')
    for number, page in enumerate(reader.pages, 1):
        if page.rotation % 360:
            errors.append(f'Стр. {number}: повёрнутая полоса вместо отдельной страницы')
        if page.get('/Annots') or page.get('/AA'):
            errors.append(f'Стр. {number}: интерактивные аннотации')
        boxes = [list(map(float, box)) for box in (page.mediabox, page.trimbox, page.bleedbox)]
        expected = [0, 0, 170 / 25.4 * 72, 240 / 25.4 * 72]
        if any(any(abs(a - b) > .1 for a, b in zip(box, expected)) for box in boxes):
            errors.append(f'Стр. {number}: неверные границы страницы')
        if page.get_contents() is not None:
            inspect(page.get_contents(), page['/Resources'])
    if bad_spaces:
        errors.append('Не преобразованные цветовые пространства: ' + ', '.join(sorted(bad_spaces)))
    raster, fonts, black_text_pages = [], {}, []
    with pymupdf.open(path) as doc:
        for number, page in enumerate(doc, 1):
            for info in page.get_image_info():
                box = pymupdf.Rect(info['bbox'])
                if box.width and box.height:
                    ppi = min(info['width'] * 72 / box.width, info['height'] * 72 / box.height)
                    raster.append({'page': number, 'ppi': round(ppi, 2)})
                    if ppi < 299.5:
                        errors.append(f'Стр. {number}: растр {ppi:.1f} ppi <300')
            for font in page.get_fonts(full=True):
                embedded = font[2] != 'Type3' and bool(doc.extract_font(font[0])[3])
                fonts[font[3]] = embedded and fonts.get(font[3], True)
                if not embedded:
                    errors.append(f'Стр. {number}: невстроенный или Type3 шрифт {font[3]}')
            for trace in page.get_texttrace():
                if re.search(r'(?:SF(?:RM|BX|TI|TT)|CM(?:R|BX|TI|TT)|CMMI|CMSY)', trace['font'], re.I):
                    colour = trace.get('color', ())
                    if isinstance(colour, (int, float)):
                        colour = (colour,)
                    if any(abs(c) > .005 for c in colour):
                        black_text_pages.append(number)
                        errors.append(f'Стр. {number}: основной текст не чёрный')
                        break
    return {'passed': not errors, 'errors': sorted(set(errors)), 'warnings': warnings,
            'pages': len(reader.pages), 'page_mm': [170, 240], 'minimum_ppi': min((x['ppi'] for x in raster), default=None),
            'raster_images': raster, 'colour_spaces': 'CMYK/Gray' if not bad_spaces else sorted(bad_spaces),
            'fonts': fonts, 'all_fonts_embedded': all(fonts.values()),
            'body_text_black_only': not black_text_pages,
            'encrypted': reader.is_encrypted,
            'interactive_annotations': sum(len(page.get('/Annots', [])) for page in reader.pages),
            'pdfx_conformance_claimed': False}


def export_press(root, source, destination, frozen):
    import pymupdf
    if teaching_hashes(root) != frozen:
        raise ValueError('Учебные материалы изменились во время сборки')
    profile = acquire_profile(root)
    gs = shutil.which('gs')
    if not gs:
        raise ValueError('Для --press-ready необходим Ghostscript (gs)')
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.press-', dir=destination.parent) as temp:
        folder = Path(temp)
        prepared, converted = folder / 'prepared.pdf', folder / 'converted.pdf'
        result = folder / destination.name
        prepare_document(source, prepared)
        command = [gs, '-dSAFER', '--permit-file-read=' + str(profile.resolve()),
                   '-dBATCH', '-dNOPAUSE', '-sDEVICE=pdfwrite', '-dCompatibilityLevel=1.6',
                   '-sColorConversionStrategy=CMYK', '-sProcessColorModel=DeviceCMYK',
                   '-dAutoRotatePages=/None', '-dPreserveAnnots=false', '-dShowAnnots=false',
                   '-dDownsampleColorImages=false', '-dDownsampleGrayImages=false', '-dDownsampleMonoImages=false',
                   '-dEmbedAllFonts=true', '-sOutputICCProfile=' + str(profile),
                   '-sOutputFile=' + str(converted), '-c', '<</NeverEmbed []>> setdistillerparams', '-f', str(prepared)]
        process = subprocess.run(command, capture_output=True, text=True)
        if process.returncode:
            raise ValueError('Ошибка Ghostscript:\n' + process.stdout + '\n' + process.stderr)
        finish_document(converted, result, profile)
        report = preflight(result)
        with pymupdf.open(source) as original, pymupdf.open(result) as master:
            report['vector_pages_preserved'] = all(not page.get_drawings() or master[i].get_drawings()
                                                   for i, page in enumerate(original))
        if not report['vector_pages_preserved']:
            report['errors'].append('Векторная страница целиком растрирована')
        report.update(profile={'name': PROFILE_NAME, 'sha256': PROFILE_SHA256, 'source': PROFILE_SOURCE, 'license': PROFILE_LICENSE},
                      assumptions=['Цветная печать на немелованной бумаге; FOGRA52 — принятое условие, а не спецификация типографии.',
                                   'Без обложки, корешка, спуска полос, вылетов и меток реза.',
                                   'Статус «Издательский макет»; официальное утверждение и полное нормативное соответствие не заявлены.'],
                      source_pdf_sha256=sha(source), pdf_sha256=sha(result), teaching_sources=frozen,
                      ghostscript=subprocess.check_output([gs, '--version'], text=True).strip(),
                      ghostscript_binary_sha256=sha(Path(gs).resolve()))
        report['text_normalization'] = 'Whitespace ignored; Latin typographic ligatures expanded; math symbols retained.'
        report['text_preserved'] = _text(prepared) == _text(result)
        if not report['text_preserved']:
            report['errors'].append('Изменился извлечённый видимый текст при цветопреобразовании')
        if teaching_hashes(root) != frozen:
            report['errors'].append('Учебные материалы изменились во время экспорта')
        report['teaching_sources_unchanged'] = teaching_hashes(root) == frozen
        report['passed'] = not report['errors']
        (folder / 'preflight.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
        lines = ['# Проверка печатного макета', '', 'Результат: ' + ('ПРОЙДЕНА' if report['passed'] else 'ОШИБКА'),
                 f'Страниц: {report["pages"]}. Формат: 170 × 240 мм. Цвет: {report["colour_spaces"]}.',
                 f'Минимальное разрешение растра: {report["minimum_ppi"]} ppi.',
                 f'Все шрифты встроены: {report["all_fonts_embedded"]}. Чёрный основной текст: {report["body_text_black_only"]}.',
                 f'Интерактивных аннотаций: {report["interactive_annotations"]}. Текст сохранён: {report["text_preserved"]}.',
                 f'Векторные страницы сохранены: {report["vector_pages_preserved"]}. Учебные исходники неизменны: {report["teaching_sources_unchanged"]}.',
                 '', *report['assumptions'], '', '## ICC-профиль', '', PROFILE_NAME, PROFILE_SOURCE, PROFILE_LICENSE,
                 '', 'SHA256: ' + PROFILE_SHA256, '', 'PDF/X-соответствие не заявлено.',
                 '', '## Ошибки', '', *report['errors'], '', '## Предупреждения', '', *report['warnings']]
        (folder / 'preflight.md').write_text('\n'.join(lines) + '\n')
        if not report['passed']:
            # Preserve diagnostics outside the destination package; never replace a good master.
            diagnostics = root / '.cache/press-failures'
            diagnostics.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(folder / 'preflight.json', diagnostics / (destination.stem + '.json'))
            shutil.copyfile(result, diagnostics / (destination.stem + '.pdf'))
            shutil.copyfile(prepared, diagnostics / (destination.stem + '-source.pdf'))
            raise ValueError('Печатная проверка не пройдена: ' + '; '.join(report['errors']))
        names = [destination.name, 'preflight.json', 'preflight.md']
        (folder / 'SHA256SUMS').write_text(''.join(f'{sha(folder / name)}  {name}\n' for name in names))
        # Reports first; publish the verified PDF last. The checksum file identifies a complete package.
        for name in ['preflight.json', 'preflight.md', destination.name, 'SHA256SUMS']:
            os.replace(folder / name, destination.parent / name)
    print(f'PRESS: {destination}', flush=True)
