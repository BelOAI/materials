"""Регрессионные проверки публикации материалов без сборки LaTeX."""

import importlib.util
import json
import yaml
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

spec = importlib.util.spec_from_file_location(
    "generate_site", Path(__file__).parents[1] / "generate-site.py"
)
site = importlib.util.module_from_spec(spec)
spec.loader.exec_module(site)


class ManifestTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.output = self.root / "_site"
        self.roots = (self.root / "course/00-topic",)
        for root in self.roots:
            root.mkdir(parents=True)
        self.patch = patch.multiple(
            site, SESSION_ROOTS=(self.root / "course",), SITE_DIR=self.output
        )
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def course(self, ids=None):
        if ids is None:
            ids = [
                f"{root.name}/{meta.parent.name}"
                for root in self.roots
                for meta in root.glob("*/material.yml")
                if not meta.parent.name.startswith("_")
            ]
        course = {
            "title": "Подготовка <&>",
            "description": "Описание подготовки",
            "weeks": [
                {
                    "slug": "topic",
                    "number": 0,
                    "title": "Тема <&>",
                    "description": "Описание темы",
                    "materials": ids,
                }
            ],
        }
        self.save_course(course)
        return course

    def save_course(self, course):
        names = []
        for week in course['weeks']:
            name = '00-topic'
            names.append(name)
            local = dict(week, materials=[value.split('/', 1)[1] for value in week['materials']])
            (self.root / 'course' / name / 'week.yml').write_text(yaml.safe_dump(local))
        (self.root / 'course/course.yml').write_text(yaml.safe_dump(dict(course, weeks=names)))

    def manifest(self):
        self.course()
        entries = site.discover_sessions()
        return site.build_manifest(entries, site.load_course(self.root, entries))

    def session(self, kind, name, extra="", pdf=False):
        folder = self.root / "course/00-topic" / ("_" + kind + "-" + name if name.startswith("_") else kind + "-" + name)
        folder.mkdir()
        (folder / "material.yml").write_text(
            f'kind: {dict(lectures="lecture", practices="practice", assignments="assignment")[kind]}\nnumber: "{site.session_number(name)}"\ntitle: "Название <&>"\ndate: "2026-10-10"\n' + extra, encoding="utf-8"
        )
        if pdf:
            dest = self.output / "pdfs/00-topic" / (kind + "-" + name + ".pdf")
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.touch()
        return folder

    def test_sort_dates_assignments_and_mixed_times(self):
        self.session("lectures", "01-slot", 'slot: "2"\n', pdf=True)
        self.session("lectures", "02-time", 'time: "12:00–13:00"\n', pdf=True)
        self.session("practices", "01-slot", 'slot: "1"\n', pdf=True)
        self.session("practices", "02-late", 'time: "14:00"\n', pdf=True)
        self.session("assignments", "01-task", "assignment_type: math\n", pdf=True)
        self.session(
            "assignments",
            "02-old",
            'date: "2026-10-09"\nassignment_type: coding\n',
            pdf=True,
        )
        self.assertEqual(
            [e["slug"] for e in site.discover_sessions()],
            [
                "00-topic/assignments-01-task",
                "00-topic/practices-02-late",
                "00-topic/lectures-01-slot",
                "00-topic/lectures-02-time",
                "00-topic/practices-01-slot",
                "00-topic/assignments-02-old",
            ],
        )

    def test_visibility_and_required_assignment_type(self):
        for name, extra in [
            ("01-hidden", "hidden: true\n"),
            ("02-disabled", "build: false\n"),
            ("_template", ""),
        ]:
            self.session("lectures", name, extra, pdf=True)
        self.session("lectures", "03-empty")
        self.session("assignments", "01-invalid", "assignment_type: other\n", pdf=True)
        self.assertEqual(site.discover_sessions(), [])

    def test_references_only_and_missing_pdf(self):
        self.session(
            "practices",
            "01-links",
            "references:\n  - kind: contest\n    url: https://example.com/contest\n",
        )
        entry = self.manifest()["materials"][0]
        self.assertNotIn("pdf", entry)
        self.assertNotIn("thumb", entry)
        self.assertEqual(entry["id"], "00-topic/practices-01-links")
        self.assertEqual(entry["references"][0]["label"], "Яндекс.Контест")

    def test_multiple_notebooks_missing_files_and_json(self):
        self.session(
            "lectures",
            "01-files",
            "materials:\n  - path: materials/a.ipynb\n    label: Первый\n  - path: materials/b.ipynb\n    label: Второй\n  - path: materials/missing.csv\n",
        )
        out = self.output / "materials/00-topic/lectures-01-files"
        out.mkdir(parents=True)
        for name in ("a.ipynb", "a.html", "b.ipynb"):
            (out / name).touch()
        thumb = self.output / "thumbs/00-topic/lectures-01-files.png"
        thumb.parent.mkdir(parents=True)
        thumb.touch()  # Старое превью без PDF не должно публиковаться.
        manifest = self.manifest()
        encoded = json.dumps(manifest, ensure_ascii=False)
        self.assertEqual(json.loads(encoded), manifest)
        self.assertEqual(manifest["version"], 2)
        entry = manifest["materials"][0]
        self.assertEqual(entry["title"], "Название <&>")
        self.assertNotIn("thumb", entry)
        self.assertEqual([m["label"] for m in entry["materials"]], ["Первый", "Второй"])
        self.assertEqual(entry["materials"][1]["open"], "")
        self.assertEqual(
            entry["materials"][0]["open"], "materials/00-topic/lectures-01-files/a.html"
        )
        self.assertNotIn("slot_index", entry)

    def test_duplicate_notebook_labels_and_encoded_paths(self):
        self.session(
            "lectures",
            "01-files",
            "materials:\n  - path: materials/a #1.ipynb\n  - path: materials/b.ipynb\n",
        )
        out = self.output / "materials/00-topic/lectures-01-files"
        out.mkdir(parents=True)
        for name in ("a #1.ipynb", "b.ipynb"):
            (out / name).touch()
        files = self.manifest()["materials"][0]["materials"]
        self.assertNotEqual(files[0]["label"], files[1]["label"])
        self.assertEqual(
            files[0]["download"], "materials/00-topic/lectures-01-files/a%20%231.ipynb"
        )

    def test_publish_manifest_shell_and_fonts(self):
        self.session("lectures", "01-topic", pdf=True)
        source = self.root / "utils/site"
        fonts = source / "fonts"
        fonts.mkdir(parents=True)
        (fonts / "test.woff2").touch()
        (source / "index.html").write_text(
            (Path(__file__).parents[3] / "utils/site/index.html").read_text(),
            encoding="utf-8",
        )
        (source / "favicon.svg").write_text("иконка", encoding="utf-8")
        assets = source / "assets/fontawesome"
        assets.mkdir(parents=True)
        (assets / "github.svg").write_text("<svg/>", encoding="utf-8")
        for filename in ("LICENSE", "LICENSE-CC-BY-4.0", "LICENSE-MIT"):
            (self.root / filename).write_bytes(
                (Path(__file__).parents[3] / filename).read_bytes()
            )
        self.course()
        with patch.multiple(
            site, REPO_ROOT=self.root, FONTS_SRC=fonts, FONTS_DEST=self.output / "fonts"
        ):
            site.main()
        data = json.loads((self.output / "materials.json").read_text())
        self.assertEqual(data["version"], 2)
        self.assertEqual(data["materials"][0]["id"], "00-topic/lectures-01-topic")
        self.assertTrue((self.output / "fonts/test.woff2").is_file())
        home = (self.output / "index.html").read_text()
        self.assertIn("Подготовка &lt;&amp;&gt;", home)
        self.assertIn('href="weeks/topic/"', home)
        week = (self.output / "weeks/topic/index.html").read_text()
        self.assertIn('href="../../pdfs/00-topic/lectures-01-topic.pdf"', week)
        self.assertIn('aria-current="page">Неделя 0', week)
        self.assertIn("Название &lt;&amp;&gt;", week)
        self.assertIn(
            '<ul class="week-resources"><li><h2 id="lecture">Лекции</h2><lecture-viewer', week
        )
        self.assertIn('<li class="material"', week)
        self.assertNotIn("<article", week)
        self.assertIn('<h1>Неделя 0 <span class="heading-topic">', week)
        self.assertIn('<span class="nav-topic">', week)
        self.assertNotIn('id="practice"', week)
        self.assertNotIn('id="assignment"', week)
        catalog = (self.output / "materials/index.html").read_text()
        self.assertIn('href="../pdfs/00-topic/lectures-01-topic.pdf"', catalog)
        self.assertIn("<catalog-controls>", catalog)
        self.assertIn('<materials-catalog root="../">', catalog)
        self.assertIn('</ul></materials-catalog>', catalog)
        for html, root, page in ((home, "./", "home"), (catalog, "../", "catalog"), (week, "../../", "topic")):
            self.assertIn(f'<course-shell root="{root}" page="{page}">', html)
            self.assertIn('<course-navigation>', html)
            self.assertIn('<details class="course-menu" open>', html)
            self.assertIn('<material-preview for="content">', html)
        self.assertIn('data-root="../"', catalog)
        self.assertNotIn('class="site-footer"', home)
        self.assertIn('href="https://github.com/BelOAI/materials"', home)
        self.assertIn('href="./license/"', home)
        self.assertIn('href="../../license/"', week)
        for label, href in (
            ("GitHub", "https://github.com/BelOAI"),
            ("Instagram", "https://instagram.com/beloaiby"),
            ("TikTok", "https://tiktok.com/@beloaiby"),
            ("Telegram", "https://t.me/beloaiby"),
        ):
            self.assertEqual(home.count(f'href="{href}"'), 2)
            self.assertIn(f'aria-label="{label} BelOAI"', home)
            self.assertIn(f'title="{label} BelOAI"', home)
        license_page = (self.output / "license/index.html").read_text()
        self.assertIn('href="../license/" aria-current="page"', license_page)
        self.assertIn('href="../LICENSE-MIT"', license_page)
        self.assertIn('href="../LICENSE-CC-BY-4.0"', license_page)
        self.assertIn('href="https://github.com/BelOAI/materials/blob/main/CONTRIBUTORS.md"', license_page)
        self.assertIn("BSD-3-Clause", license_page)
        self.assertIn('href="../assets/fontawesome/LICENSE.txt"', license_page)
        self.assertEqual((self.output / "assets/fontawesome/github.svg").read_text(), "<svg/>")
        for filename in ("LICENSE", "LICENSE-CC-BY-4.0", "LICENSE-MIT"):
            self.assertEqual((self.output / ("LICENSE.txt" if filename == "LICENSE" else filename)).read_bytes(), (self.root / filename).read_bytes())

    def test_notebook_preview_target_and_pdf_priority(self):
        self.session(
            "practices",
            "01-files",
            "materials:\n  - path: materials/a.ipynb\n  - path: materials/b.ipynb\n",
        )
        out = self.output / "materials/00-topic/practices-01-files"
        out.mkdir(parents=True)
        for name in ("a.ipynb", "b.ipynb"):
            (out / name).touch()
        preview = self.output / "thumbs/00-topic/practices-01-files/a.ipynb.svg"
        preview.parent.mkdir(parents=True)
        preview.touch()
        entry = self.manifest()["materials"][0]
        self.assertEqual(entry["thumb"], "thumbs/00-topic/practices-01-files/a.ipynb.svg")
        self.assertEqual(entry["thumb_href"], "materials/00-topic/practices-01-files/a.ipynb")
        (out / "a.html").touch()
        entry = self.manifest()["materials"][0]
        self.assertEqual(entry["thumb_href"], "materials/00-topic/practices-01-files/a.html")
        pdf = self.output / "pdfs/00-topic/practices-01-files.pdf"
        pdf.parent.mkdir(parents=True)
        pdf.touch()
        thumb = self.output / "thumbs/00-topic/practices-01-files.png"
        thumb.touch()
        entry = self.manifest()["materials"][0]
        self.assertEqual(entry["thumb"], "thumbs/00-topic/practices-01-files.png")
        self.assertEqual(entry["thumb_href"], "pdfs/00-topic/practices-01-files.pdf")

    def test_assignment_notebook_preview_and_pdf_priority(self):
        self.session(
            "assignments",
            "04-knn",
            "assignment_type: coding\nmaterials:\n  - path: materials/task.ipynb\n",
        )
        out = self.output / "materials/00-topic/assignments-04-knn"
        out.mkdir(parents=True)
        (out / "task.ipynb").touch()
        preview = self.output / "thumbs/00-topic/assignments-04-knn/task.ipynb.svg"
        preview.parent.mkdir(parents=True)
        preview.touch()

        entry = self.manifest()["materials"][0]
        self.assertEqual(entry["kind"], "assignment")
        self.assertEqual(entry["thumb"], "thumbs/00-topic/assignments-04-knn/task.ipynb.svg")
        self.assertEqual(entry["thumb_href"], "materials/00-topic/assignments-04-knn/task.ipynb")

        pdf = self.output / "pdfs/00-topic/assignments-04-knn.pdf"
        pdf.parent.mkdir(parents=True)
        pdf.touch()
        pdf_thumb = self.output / "thumbs/00-topic/assignments-04-knn.png"
        pdf_thumb.parent.mkdir(parents=True, exist_ok=True)
        pdf_thumb.touch()
        entry = self.manifest()["materials"][0]
        self.assertEqual(entry["thumb"], "thumbs/00-topic/assignments-04-knn.png")
        self.assertEqual(entry["thumb_href"], "pdfs/00-topic/assignments-04-knn.pdf")


if __name__ == "__main__":
    unittest.main()
