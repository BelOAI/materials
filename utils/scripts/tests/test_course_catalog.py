"""Недельный каталог проверяется на временных материалах."""
import sys
import tempfile
import unittest
from pathlib import Path
import yaml
sys.path.insert(0, str(Path(__file__).parents[1]))
from course_catalog import load_course, read_yaml, session_directories


class CourseCatalogTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.course = self.root / 'course'
        self.course.mkdir()
        self.entries = []
        self.names = []

    def write(self, path, data):
        path.write_text(yaml.safe_dump(data, allow_unicode=True))

    def week(self, name, number, kinds):
        folder = self.course / name
        folder.mkdir()
        materials = []
        for index, kind in enumerate(kinds):
            material = f'{index}-{kind}'
            session = folder / material
            session.mkdir()
            (session / 'material.yml').write_text(f'kind: {kind}\nbuild: true\n')
            materials.append(material)
            self.entries.append(dict(slug=f'{name}/{material}', kind=kind, pdf=f'pdfs/{name}/{material}.pdf'))
        week = dict(slug=name, number=number, title='Тема', description='Описание', materials=materials)
        self.write(folder / 'week.yml', week)
        self.names.append(name)
        self.write(self.course / 'course.yml', dict(title='Курс', description='Описание', weeks=self.names))
        return folder, week

    def load(self):
        return load_course(self.root, self.entries)

    def test_local_order_and_zero_without_lecture(self):
        self.week('second', 2, ['assignment', 'lecture', 'practice'])
        self.week('start', 0, ['assignment'])
        course = self.load()
        self.assertEqual([w['number'] for w in course['weeks']], [2, 0])
        self.assertEqual(course['weeks'][0]['materials'], [e['slug'] for e in self.entries[:3]])

    def test_required_single_published_lecture_pdf(self):
        folder, week = self.week('topic', 1, ['practice'])
        with self.assertRaisesRegex(ValueError, 'одну лекцию'):
            self.load()
        (folder / '0-practice/material.yml').write_text('kind: lecture\n')
        self.entries[0].pop('pdf')
        with self.assertRaisesRegex(ValueError, 'PDF'):
            self.load()
        self.entries[0]['pdf'] = 'lecture.pdf'
        self.assertEqual(len(self.load()['weeks']), 1)
        (folder / '0-practice/material.yml').write_text('kind: lecture\nhidden: true\n')
        self.assertEqual(self.load()['weeks'], [])
        (folder / 'extra').mkdir()
        (folder / 'extra/material.yml').write_text('kind: lecture\n')
        week['materials'].append('extra')
        self.write(folder / 'week.yml', week)
        with self.assertRaisesRegex(ValueError, 'одну лекцию'):
            self.load()

    def test_missing_duplicate_unassigned_and_escaping_paths(self):
        folder, week = self.week('topic', 0, ['practice'])
        original = list(week['materials'])
        for value in (['missing'], original * 2, ['../topic/0-practice'], []):
            week['materials'] = value
            self.write(folder / 'week.yml', week)
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.load()
        self.write(self.course / 'course.yml', dict(title='Курс', description='Описание', weeks=['../outside']))
        with self.assertRaises(ValueError):
            self.load()

    def test_unique_numbers_slugs_and_week_folders(self):
        self.week('one', 0, ['practice'])
        folder, week = self.week('two', 0, ['practice'])
        with self.assertRaises(ValueError):
            self.load()
        week['number'] = 1
        week['slug'] = 'one'
        self.write(folder / 'week.yml', week)
        with self.assertRaises(ValueError):
            self.load()
        self.names.pop()
        self.write(self.course / 'course.yml', dict(title='Курс', description='Описание', weeks=self.names))
        with self.assertRaisesRegex(ValueError, 'без недели|вне course'):
            self.load()

    def test_hidden_disabled_and_templates(self):
        folder, week = self.week('topic', 0, ['practice', 'assignment', 'practice'])
        (folder / '0-practice/material.yml').write_text('kind: practice\nhidden: true\n')
        (folder / '1-assignment/material.yml').write_text('kind: assignment\nbuild: false\n')
        template = self.course / '_templates/lecture'
        template.mkdir(parents=True)
        (template / 'material.yml').write_text('kind: lecture\n')
        self.assertEqual(len(session_directories(self.course)), 3)
        self.assertEqual(self.load()['weeks'][0]['materials'], ['topic/2-practice'])

    def test_yaml_duplicate_keys_rejected(self):
        path = self.course / 'course.yml'
        path.write_text('title: First\ntitle: Second\n')
        with self.assertRaises(ValueError):
            read_yaml(path)

    def test_static_week_neighbors_viewer_and_stale_pages(self):
        import shutil
        from course_site import publish_pages
        self.week('start', 0, ['practice'])
        self.week('topic', 1, ['lecture', 'assignment'])
        course = self.load()
        course['description'] = 'Course description marker.'
        for week in course['weeks']:
            week['description'] = 'Week description marker.'
        for entry in self.entries:
            entry.update(id=entry['slug'], title='Материал <&>', number='1', date='', time='', description='Material description marker.', subtitle='Subtitle fixture.', materials=[], references=[], thumb='preview.png')
        template = self.root / 'utils/site'
        template.mkdir(parents=True)
        shutil.copy(Path(__file__).parents[3] / 'utils/site/index.html', template / 'index.html')
        output = self.root / '_site'
        stale = output / 'weeks/stale/index.html'
        stale.parent.mkdir(parents=True)
        stale.touch()
        publish_pages(self.root, output, dict(course=course, materials=self.entries))
        self.assertFalse(stale.exists())
        start = (output / 'weeks/start/index.html').read_text()
        topic = (output / 'weeks/topic/index.html').read_text()
        self.assertIn('href="../topic/" rel="next"', start)
        self.assertNotIn('rel="prev"', start)
        self.assertIn('href="../start/" rel="prev"', topic)
        self.assertNotIn('rel="next"', topic)
        self.assertNotIn('<lecture-viewer', start)
        self.assertIn('<lecture-viewer src="../../pdfs/topic/0-lecture.pdf">', topic)
        self.assertIn('class="slide-fallback"', topic)
        self.assertLess(topic.index('<lecture-viewer'), topic.index('data-kind="lecture"'))
        lecture = self.entries[1]
        from course_site import render_material
        self.assertNotIn('data-preview=', render_material(lecture, '../../'))
        self.assertIn('data-preview=', render_material(self.entries[0], '../../'))
        catalog = (output / 'materials/index.html').read_text()
        home = (output / 'index.html').read_text()
        self.assertIn('name="description" content="Course description marker."', home)
        self.assertIn('name="description" content="Week description marker."', topic)
        for html in [home, start, topic, catalog]:
            body = html.split('<body', 1)[1]
            for marker in ['Course description marker.', 'Week description marker.', 'Material description marker.']:
                self.assertNotIn(marker, body)
        self.assertIn('Subtitle fixture.', catalog)
        for path, root in [('index.html', './'), ('materials/index.html', '../'),
                           ('weeks/topic/index.html', '../../'), ('license/index.html', '../')]:
            html = (output / path).read_text()
            navigation = html.split('<course-navigation', 1)[1].split('</course-navigation>', 1)[0]
            self.assertIn(f'href="{root}handbooks/"', navigation)
        self.assertNotIn('data-preview=', catalog.split('data-kind="lecture"', 1)[1].split('</li>', 1)[0])
        self.assertLess(topic.index('<lecture-viewer'), topic.index('id="assignment"'))
        self.assertIn('Материал &lt;&amp;&gt;', topic)


    def test_duplicate_and_unsafe_legacy_identifiers(self):
        folder, week = self.week('topic', 0, ['practice', 'assignment'])
        for material in week['materials']:
            (folder / material / 'material.yml').write_text('kind: practice\nlegacy_id: practices/01-old\n')
        with self.assertRaisesRegex(ValueError, 'Повтор legacy_id'):
            self.load()
        (folder / week['materials'][0] / 'material.yml').write_text('kind: practice\nlegacy_id: ../outside\n')
        with self.assertRaisesRegex(ValueError, 'Неверный legacy_id'):
            self.load()


    def test_unlisted_drafts_and_hidden_materials_do_not_block_publication(self):
        folder, week = self.week('topic', 0, ['practice'])
        for name, flag in [('draft', 'build: false'), ('hidden', 'hidden: true')]:
            session = folder / name
            session.mkdir()
            (session / 'material.yml').write_text(f'{flag}\n')
        self.assertEqual(self.load()['weeks'][0]['materials'], ['topic/0-practice'])
