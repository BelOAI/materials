"""Интеграция выбора PDF со сборкой; внешние утилиты заменены дублёрами."""
import os
import json
from urllib.parse import unquote
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from repo_paths import REPO_ROOT as ROOT


class PdfPipelineTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        shutil.copytree(ROOT / 'utils/scripts', self.root / 'utils/scripts', ignore=shutil.ignore_patterns('__pycache__'))
        shutil.copytree(ROOT / 'utils/site/assets', self.root / 'utils/site/assets')
        (self.root / 'build').mkdir()
        shutil.copy(ROOT / 'build/Makefile', self.root / 'build/Makefile')
        self.bin = self.root / 'bin'
        self.bin.mkdir()
        for name, body in {
            'pdfinfo': "import sys\nfrom pathlib import Path\ndata = Path(sys.argv[1]).read_bytes()\nif not data.startswith(b'%PDF-'): sys.exit(1)\nprint('Pages: 0' if b'empty' in data else 'Pages: 1')\nprint('Encrypted: yes' if b'encrypted' in data else 'Encrypted: no')\n",
            'pdftoppm': "import sys\nfrom pathlib import Path\nPath(sys.argv[-1] + '.png').write_bytes(b'preview')\n",
            'pdflatex': "from pathlib import Path\nPath('main.pdf').write_bytes(b'%PDF-tex')\nwith Path('tex-runs').open('a') as f: f.write('run\\n')\n",
        }.items():
            p = self.bin / name
            p.write_text(f'#!{sys.executable}\n' + body)
            p.chmod(0o755)
        self.env = dict(os.environ, PATH=str(self.bin) + os.pathsep + os.environ['PATH'])

    def session(self, kind='lectures', extra=''):
        p = self.root / "course" / kind / '01-тема с пробелами'
        p.mkdir(parents=True)
        (p / 'meta.yaml').write_text('title: Тема\nbuild: true\n' + extra)
        return p

    def run_build(self, session, ok=True):
        r = subprocess.run([sys.executable, str(self.root / 'utils/scripts/build-session.py'), str(session)], env=self.env, capture_output=True, text=True)
        self.assertEqual(r.returncode == 0, ok, r.stdout + r.stderr)
        return r

    def target(self, session, kind='pdfs', ext='.pdf'):
        return self.root / '_site' / kind / session.parent.name / (session.name + ext)

    def test_import_all_kinds_without_tex(self):
        for kind in ('lectures', 'practices', 'assignments'):
            with self.subTest(kind=kind):
                s = self.session(kind, 'pdf: materials/Свои слайды.PDF\nassignment_type: math\nmaterials:\n  - path: materials/data.csv\n')
                (s / 'materials').mkdir()
                source = s / 'materials/Свои слайды.PDF'
                source.write_bytes(b'%PDF-imported')
                (s / 'materials/data.csv').write_text('a,b\n1,2\n')
                self.run_build(s)
                self.assertEqual(self.target(s).read_bytes(), source.read_bytes())
                self.assertTrue(self.target(s, 'thumbs', '.png').exists())
                self.assertTrue((self.root / '_site/materials' / kind / s.name / 'data.csv').exists())
                self.assertFalse((s / 'tex-runs').exists())

    def test_assignment_notebook_preview_without_pdf(self):
        session = self.session(
            'assignments',
            'assignment_type: coding\nmaterials:\n  - path: materials/task.ipynb\n',
        )
        (session / 'materials').mkdir()
        (session / 'materials/task.ipynb').write_text(
            json.dumps({'cells': [{'cell_type': 'code', 'source': 'answer = 42'}]}),
            encoding='utf-8',
        )
        self.run_build(session)
        preview = self.root / '_site/thumbs/assignments' / session.name / 'task.ipynb.svg'
        svg = preview.read_text(encoding='utf-8')
        self.assertIn('answer =', svg)
        self.assertIn('>42</tspan>', svg)
        self.assertFalse(self.target(session, 'thumbs', '.png').exists())

    def test_manifest_for_imported_pdf(self):
        for kind in ('lectures', 'practices', 'assignments'):
            session = self.session(kind, 'pdf: own.pdf\nassignment_type: math\n')
            (session / 'own.pdf').write_bytes(b'%PDF-imported')
            self.run_build(session)
        course = {"title": "Подготовка", "description": "Описание", "weeks": [{
            "slug": "topic", "number": 0, "title": "Тема", "description": "Описание",
            "materials": [f"{kind}/01-тема с пробелами" for kind in ("lectures", "practices", "assignments")],
        }]}
        (self.root / 'course/course.json').write_text(json.dumps(course), encoding='utf-8')
        code = "import json,runpy; from pathlib import Path; m=runpy.run_path('utils/scripts/generate-site.py'); entries=m['discover_sessions'](); print(json.dumps(m['build_manifest'](entries, m['load_course'](Path('.'), entries))))"
        result = subprocess.run([sys.executable, '-c', code], cwd=self.root, capture_output=True, text=True, check=True)
        manifest = json.loads(result.stdout)
        self.assertEqual(manifest['version'], 2)
        self.assertEqual(len(manifest['materials']), 3)
        for entry in manifest['materials']:
            self.assertIn('pdf', entry)
            self.assertEqual(entry['thumb_href'], entry['pdf'])
            self.assertTrue((self.root / '_site' / unquote(entry['pdf'])).is_file())
            self.assertTrue((self.root / '_site' / unquote(entry['thumb'])).is_file())

    def test_precedence_local_tex_and_mode_changes(self):
        s = self.session(extra='pdf: slides.pdf\n')
        (s / 'slides.pdf').write_bytes(b'%PDF-imported')
        (s / 'main.tex').write_text('test')
        self.run_build(s)
        subprocess.run(['make', '-f', 'build/Makefile', 'tex', f'DIR={s}'], cwd=self.root, env=self.env, check=True, capture_output=True)
        self.assertEqual(self.target(s).read_bytes(), b'%PDF-imported')
        self.assertEqual((s / 'main.pdf').read_bytes(), b'%PDF-tex')
        (s / 'meta.yaml').write_text('title: Тема\n')
        self.run_build(s)
        self.assertEqual(self.target(s).read_bytes(), b'%PDF-tex')
        (s / 'main.tex').unlink()
        self.run_build(s)
        self.assertFalse(self.target(s).exists())
        self.assertFalse(self.target(s, 'thumbs', '.png').exists())
        self.assertTrue((s / 'slides.pdf').exists())

    def test_invalid_source_never_falls_back(self):
        for value in ('missing.pdf', 'broken.pdf', '../outside.pdf', 'main.pdf', '/tmp/file.pdf', ''):
            with self.subTest(value=value):
                if hasattr(self, 's'):
                    shutil.rmtree(self.s)
                self.s = self.session(extra=f'pdf: "{value}"\n')
                (self.s / 'main.tex').write_text('test')
                (self.s / 'broken.pdf').write_bytes(b'broken')
                dest = self.target(self.s)
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(b'%PDF-stale')
                r = self.run_build(self.s, ok=False)
                self.assertIn('Ошибка сборки', r.stderr)
                self.assertFalse(dest.exists())
                self.assertFalse((self.s / 'tex-runs').exists())

    def test_empty_and_encrypted_pdf(self):
        session = self.session(extra='pdf: own.pdf\n')
        for content in (b'%PDF-empty', b'%PDF-encrypted'):
            (session / 'own.pdf').write_bytes(content)
            self.run_build(session, ok=False)
            self.assertFalse(self.target(session).exists())

    def test_pdfinfo_required_for_import(self):
        session = self.session(extra='pdf: own.pdf\n')
        (session / 'own.pdf').write_bytes(b'%PDF-imported')
        (self.bin / 'pdfinfo').unlink()
        self.env['PATH'] = str(self.bin)
        result = self.run_build(session, ok=False)
        self.assertIn('pdfinfo', result.stderr)

    def test_symlink_outside_is_rejected(self):
        s = self.session(extra='pdf: slides.pdf\n')
        outside = self.root / 'outside.pdf'
        outside.write_bytes(b'%PDF-external')
        (s / 'slides.pdf').symlink_to(outside)
        self.run_build(s, ok=False)

    def test_global_flags_and_deleted_sessions(self):
        s = self.session(extra='pdf: slides.pdf\nhidden: true\n')
        (s / 'slides.pdf').write_bytes(b'%PDF-hidden')
        for name, extra in (('_template', ''), ('02-disabled', 'build: false\n')):
            p = self.root / 'course/lectures' / name
            p.mkdir()
            (p / 'meta.yaml').write_text(extra + 'pdf: missing.pdf\n')
        stale = self.root / '_site/pdfs/lectures/deleted.pdf'
        stale.parent.mkdir(parents=True)
        stale.write_bytes(b'old')
        subprocess.run(['bash', str(self.root / 'utils/scripts/build-all.sh')], env=self.env, check=True, capture_output=True)
        self.assertFalse(stale.exists())
        self.assertTrue(self.target(s).exists())
        subprocess.run(['make', '-f', 'build/Makefile', 'clean'], cwd=self.root, env=self.env, check=True, capture_output=True)
        self.assertTrue((s / 'slides.pdf').exists())

    def cached_tex_session(self):
        session = self.session()
        (session / 'main.tex').write_text('source')
        counter = self.root / 'tex-count'
        (self.bin / 'pdflatex').write_text(
            f'#!{sys.executable}\nfrom pathlib import Path\n'
            "Path('main.pdf').write_bytes(b'%PDF-tex')\n"
            f"with Path({str(counter)!r}).open('a') as stream: stream.write('run\\n')\n"
        )
        return session, counter

    def test_warm_cache_restores_after_output_cleanup(self):
        session, counter = self.cached_tex_session()
        self.run_build(session)
        outputs = self.root / '_site'
        before = {str(p.relative_to(outputs)): p.read_bytes() for p in outputs.rglob('*') if p.is_file()}
        shutil.rmtree(outputs)
        (session / 'main.pdf').unlink()
        result = self.run_build(session)
        self.assertIn('CACHE HIT sessions', result.stdout)
        self.assertEqual((session / 'main.pdf').read_bytes(), self.target(session).read_bytes())
        self.assertEqual(counter.read_text().splitlines(), ['run', 'run'])
        self.assertEqual(before, {str(p.relative_to(outputs)): p.read_bytes() for p in outputs.rglob('*') if p.is_file()})

    def test_source_style_environment_and_corrupt_cache_rebuild(self):
        session, counter = self.cached_tex_session()
        self.run_build(session)
        (session / 'main.tex').write_text('changed')
        self.assertIn('CACHE MISS', self.run_build(session).stdout)
        style = self.root / 'utils/latex/tex/latex/test.sty'
        style.parent.mkdir(parents=True)
        style.write_text('style')
        self.assertIn('CACHE MISS', self.run_build(session).stdout)
        self.env['BUILD_ENV_ID'] = 'new-image'
        self.assertIn('CACHE MISS', self.run_build(session).stdout)
        for file in (self.root / '.cache/build/sessions').rglob('*.pdf'):
            file.write_bytes(b'corrupt')
        self.assertIn('CACHE MISS', self.run_build(session).stdout)
        self.assertEqual(len(counter.read_text().splitlines()), 10)

    def test_cached_session_disabling_and_deletion_remove_outputs(self):
        session = self.session(extra='pdf: own.pdf\n')
        (session / 'own.pdf').write_bytes(b'%PDF-good')
        self.run_build(session)
        (session / 'meta.yaml').write_text('build: false\n')
        subprocess.run(['bash', str(self.root / 'utils/scripts/build-all.sh')], env=self.env, check=True, capture_output=True)
        self.assertFalse(self.target(session).exists())
        shutil.rmtree(session)
        subprocess.run(['bash', str(self.root / 'utils/scripts/build-all.sh')], env=self.env, check=True, capture_output=True)
        self.assertFalse(self.target(session).exists())
