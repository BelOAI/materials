"""Распределённые метаданные курса и расположение материалов."""
import re
import yaml
from handbook_catalog import MetadataLoader
from meta_parser import get_flat, parse_meta

KINDS = {'lecture', 'practice', 'assignment'}


def read_yaml(path):
    try:
        value = yaml.load(path.read_text(encoding='utf-8'), Loader=MetadataLoader)
    except yaml.YAMLError as error:
        raise ValueError(f'Неверный YAML: {path}: {error}') from error
    if not isinstance(value, dict):
        raise ValueError(f'Ожидается объект YAML: {path}')
    return value


def local_directory(base, name):
    if (not isinstance(name, str) or not name or name.startswith('_')
            or '/' in name or '\\' in name or name in {'.', '..'}):
        raise ValueError(f'Неверное имя папки: {name!r}')
    path = base / name
    if not path.is_dir() or not path.resolve().is_relative_to(base.resolve()):
        raise ValueError(f'Папка отсутствует или выходит за пределы курса: {path}')
    return path


def session_slug(session):
    """Материал находится непосредственно в папке недели."""
    if session.parent.parent.name != 'course' or not (session / 'material.yml').is_file():
        raise ValueError(f'Ожидается course/<неделя>/<материал>/material.yml: {session}')
    return f'{session.parent.name}/{session.name}'


def session_directories(course):
    return sorted(p.parent for p in course.glob('*/*/material.yml')
                  if not any(part.startswith('_') for part in p.relative_to(course).parts))


def material_is_public(meta):
    return get_flat(meta, 'build', 'true').lower() != 'false' and get_flat(meta, 'hidden', 'false').lower() != 'true'


def load_course(root, entries):
    base = root / 'course'
    course = read_yaml(base / 'course.yml')
    if not all(isinstance(course.get(k), str) and course[k].strip() for k in ('title', 'description')) or not isinstance(course.get('weeks'), list):
        raise ValueError('В course.yml необходимы title, description и weeks')
    available = {e['slug']: e for e in entries}
    assigned, slugs, numbers, folders = set(), set(), set(), set()
    weeks = []
    aliases = set()
    for name in course['weeks']:
        folder = local_directory(base, name)
        if name in folders:
            raise ValueError(f'Повтор недели: {name}')
        folders.add(name)
        week = read_yaml(folder / 'week.yml')
        if (not all(isinstance(week.get(k), str) and week[k].strip() for k in ('slug', 'title', 'description'))
                or not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', week['slug'])):
            raise ValueError(f'Некорректная неделя: {folder}')
        number = week.get('number')
        if type(number) is not int or number < 0 or number in numbers or week['slug'] in slugs:
            raise ValueError('Номера и slug недель должны быть уникальными')
        numbers.add(number)
        slugs.add(week['slug'])
        if not isinstance(week.get('materials'), list):
            raise ValueError('Неделя должна содержать список materials')
        visible, lectures = [], []
        public_lectures = []
        for material in week['materials']:
            session = local_directory(folder, material)
            identifier = session_slug(session)
            if identifier in assigned:
                raise ValueError(f'Материал назначен повторно: {identifier}')
            assigned.add(identifier)
            meta = parse_meta(session / 'material.yml')
            alias = legacy_id(meta)
            if alias and alias in aliases:
                raise ValueError(f'Повтор legacy_id: {alias}')
            if alias:
                aliases.add(alias)
            kind = get_flat(meta, 'kind')
            if kind not in KINDS:
                raise ValueError(f'Некорректный kind: {identifier}')
            public = material_is_public(meta)
            if kind == 'lecture':
                lectures.append(identifier)
                if public:
                    public_lectures.append(identifier)
            if public and identifier in available:
                visible.append(identifier)
        if len(lectures) > 1 or (number != 0 and len(lectures) != 1):
            raise ValueError(f'Неделя {number} должна содержать одну лекцию (кроме недели 0)')
        if visible and number != 0 and (len(public_lectures) != 1 or not available.get(public_lectures[0], {}).get('pdf')):
            raise ValueError(f'Для недели {number} необходим опубликованный PDF лекции')
        if visible:
            weeks.append({k: week[k] for k in ('slug', 'number', 'title', 'description')} | {'materials': visible})
    known = {session_slug(p) for p in session_directories(base)
             if material_is_public(parse_meta(p / 'material.yml'))}
    if overlap := aliases & known:
        raise ValueError('legacy_id совпадает с материалом: ' + ', '.join(sorted(overlap)))
    if missing := known - assigned:
        raise ValueError('Материалы без недели: ' + ', '.join(sorted(missing)))
    week_folders = {p.parent.name for p in base.glob('*/week.yml') if not p.parent.name.startswith('_')}
    if missing := week_folders - folders:
        raise ValueError('Недели вне course.yml: ' + ', '.join(sorted(missing)))
    return {k: course[k] for k in ('title', 'description')} | {'weeks': weeks}


def legacy_id(meta):
    value = get_flat(meta, 'legacy_id')
    if value and not re.fullmatch(r'(?:lectures|practices|assignments)/[a-z0-9]+(?:-[a-z0-9]+)*', value):
        raise ValueError(f'Неверный legacy_id: {value}')
    return value


def publish_legacy_resources(session, output):
    """Сохраняем ранее опубликованные прямые ссылки на файлы."""
    import shutil
    source_id = session_slug(session)
    alias = legacy_id(parse_meta(session / 'material.yml'))
    if not alias:
        return
    if alias == source_id:
        raise ValueError(f'legacy_id совпадает с материалом: {alias}')
    for category, suffix in (('pdfs', '.pdf'), ('thumbs', '.png'), ('materials', ''), ('thumbs', '')):
        source = output / category / (source_id + suffix)
        target = output / category / (alias + suffix)
        if target.is_dir():
            shutil.rmtree(target)
        else:
            target.unlink(missing_ok=True)
        if source.is_file():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
        elif source.is_dir():
            shutil.copytree(source, target)
