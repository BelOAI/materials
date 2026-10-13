"""Регрессионные проверки публикации материалов без сборки LaTeX."""

import importlib.util
import json
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
        self.roots = tuple(
            self.root / kind for kind in ("lectures", "practices", "assignments")
        )
        for root in self.roots:
            root.mkdir()
        self.patch = patch.multiple(
            site, SESSION_ROOTS=self.roots, SITE_DIR=self.output
        )
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def course(self, ids=None):
        if ids is None:
            ids = [
                f"{root.name}/{meta.parent.name}"
                for root in self.roots
                for meta in root.glob("*/meta.yaml")
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
        (self.root / "course.json").write_text(json.dumps(course), encoding="utf-8")
        return course

    def manifest(self):
        self.course()
        entries = site.discover_sessions()
        return site.build_manifest(entries, site.load_course(self.root, entries))

    def session(self, kind, name, extra="", pdf=False):
        folder = self.root / kind / name
        folder.mkdir()
        (folder / "meta.yaml").write_text(
            'title: "Название <&>"\ndate: "2026-10-10"\n' + extra, encoding="utf-8"
        )
        if pdf:
            dest = self.output / "pdfs" / kind / (name + ".pdf")
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
                "assignments/01-task",
                "practices/02-late",
                "lectures/01-slot",
                "lectures/02-time",
                "practices/01-slot",
                "assignments/02-old",
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
        self.assertEqual(entry["id"], "practices/01-links")
        self.assertEqual(entry["references"][0]["label"], "Яндекс.Контест")

    def test_multiple_notebooks_missing_files_and_json(self):
        self.session(
            "lectures",
            "01-files",
            "materials:\n  - path: materials/a.ipynb\n    label: Первый\n  - path: materials/b.ipynb\n    label: Второй\n  - path: materials/missing.csv\n",
        )
        out = self.output / "materials/lectures/01-files"
        out.mkdir(parents=True)
        for name in ("a.ipynb", "a.html", "b.ipynb"):
            (out / name).touch()
        thumb = self.output / "thumbs/lectures/01-files.png"
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
            entry["materials"][0]["open"], "materials/lectures/01-files/a.html"
        )
        self.assertNotIn("slot_index", entry)

    def test_duplicate_notebook_labels_and_encoded_paths(self):
        self.session(
            "lectures",
            "01-files",
            "materials:\n  - path: materials/a #1.ipynb\n  - path: materials/b.ipynb\n",
        )
        out = self.output / "materials/lectures/01-files"
        out.mkdir(parents=True)
        for name in ("a #1.ipynb", "b.ipynb"):
            (out / name).touch()
        files = self.manifest()["materials"][0]["materials"]
        self.assertNotEqual(files[0]["label"], files[1]["label"])
        self.assertEqual(
            files[0]["download"], "materials/lectures/01-files/a%20%231.ipynb"
        )

    def test_publish_manifest_shell_and_fonts(self):
        self.session("lectures", "01-topic", pdf=True)
        source = self.root / "site"
        fonts = source / "fonts"
        fonts.mkdir(parents=True)
        (fonts / "test.woff2").touch()
        (source / "index.html").write_text(
            (Path(__file__).parents[2] / "site/index.html").read_text(),
            encoding="utf-8",
        )
        (source / "favicon.svg").write_text("иконка", encoding="utf-8")
        assets = source / "assets/fontawesome"
        assets.mkdir(parents=True)
        (assets / "github.svg").write_text("<svg/>", encoding="utf-8")
        for filename in ("LICENSE-CC-BY-4.0", "LICENSE-MIT"):
            (self.root / filename).write_bytes(
                (Path(__file__).parents[2] / filename).read_bytes()
            )
        self.course()
        with patch.multiple(
            site, REPO_ROOT=self.root, FONTS_SRC=fonts, FONTS_DEST=self.output / "fonts"
        ):
            site.main()
        data = json.loads((self.output / "materials.json").read_text())
        self.assertEqual(data["version"], 2)
        self.assertEqual(data["materials"][0]["id"], "lectures/01-topic")
        self.assertTrue((self.output / "fonts/test.woff2").is_file())
        home = (self.output / "index.html").read_text()
        self.assertIn("Подготовка &lt;&amp;&gt;", home)
        self.assertIn('href="weeks/topic/"', home)
        week = (self.output / "weeks/topic/index.html").read_text()
        self.assertIn('href="../../pdfs/lectures/01-topic.pdf"', week)
        self.assertIn('aria-current="page">Неделя 0', week)
        self.assertIn("Название &lt;&amp;&gt;", week)
        self.assertIn(
            '<ul class="week-resources"><li><span id="lecture">Лекции</span><ul>', week
        )
        self.assertIn('<li class="material"', week)
        self.assertNotIn("<article", week)
        self.assertIn('<h1>Неделя 0 <span class="heading-topic">', week)
        self.assertIn('<span class="nav-topic">', week)
        self.assertNotIn('id="practice"', week)
        self.assertNotIn('id="assignment"', week)
        catalog = (self.output / "materials/index.html").read_text()
        self.assertIn('href="../pdfs/lectures/01-topic.pdf"', catalog)
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
        self.assertIn("Авторы BelOAI", license_page)
        self.assertIn('href="https://github.com/BelOAI/materials/blob/main/CONTRIBUTORS.md"', license_page)
        self.assertNotIn("для каждой недели изучите лекции", home)
        self.assertIn("BSD-3-Clause", license_page)
        self.assertIn('href="../assets/fontawesome/LICENSE.txt"', license_page)
        self.assertEqual((self.output / "assets/fontawesome/github.svg").read_text(), "<svg/>")
        for filename in ("LICENSE-CC-BY-4.0", "LICENSE-MIT"):
            self.assertEqual((self.output / filename).read_bytes(), (self.root / filename).read_bytes())

    def test_course_validation(self):
        self.session("lectures", "01-topic", pdf=True)
        self.session("practices", "01-topic", pdf=True)
        ids = ["lectures/01-topic", "practices/01-topic"]
        original = self.course(ids)
        cases = []
        for change in (
            "missing",
            "unknown",
            "duplicate",
            "slug",
            "number",
            "repeat-week",
            "description",
        ):
            course = json.loads(json.dumps(original))
            week = course["weeks"][0]
            if change == "missing":
                week["materials"].pop()
            elif change == "unknown":
                week["materials"].append("lectures/does-not-exist")
            elif change == "duplicate":
                week["materials"].append(ids[0])
            elif change == "slug":
                week["slug"] = "../bad"
            elif change == "number":
                week["number"] = True
            elif change == "description":
                week["description"] = ""
            else:
                course["weeks"].append(dict(week))
            cases.append(course)
        for course in cases:
            with self.subTest(course=course):
                (self.root / "course.json").write_text(
                    json.dumps(course), encoding="utf-8"
                )
                with self.assertRaises(ValueError):
                    site.load_course(self.root, site.discover_sessions())

    def test_course_visibility_order_and_material_without_built_resources(self):
        self.session("lectures", "01-topic", pdf=True)
        self.session("lectures", "02-hidden", "hidden: true", pdf=True)
        self.session("lectures", "03-disabled", "build: false", pdf=True)
        self.session("practices", "01-empty")
        course = self.course(
            ["lectures/03-disabled", "lectures/02-hidden", "lectures/01-topic"]
        )
        with self.assertRaisesRegex(ValueError, "practices/01-empty"):
            site.load_course(self.root, site.discover_sessions())
        course["weeks"][0]["materials"].append("practices/01-empty")
        course["weeks"].append(
            {
                "slug": "empty",
                "number": 1,
                "title": "Пустая",
                "description": "Описание",
                "materials": [],
            }
        )
        (self.root / "course.json").write_text(json.dumps(course), encoding="utf-8")
        published = site.load_course(self.root, site.discover_sessions())
        self.assertEqual(len(published["weeks"]), 1)
        self.assertEqual(published["weeks"][0]["materials"], ["lectures/01-topic"])
        self.session("lectures", "04-second", pdf=True)
        course["weeks"][0]["materials"].insert(0, "lectures/04-second")
        (self.root / "course.json").write_text(json.dumps(course), encoding="utf-8")
        published = site.load_course(self.root, site.discover_sessions())
        self.assertEqual(
            published["weeks"][0]["materials"],
            ["lectures/04-second", "lectures/01-topic"],
        )

    def test_week_neighbors_and_removal_of_stale_pages(self):
        self.session("lectures", "01-topic", pdf=True)
        self.session(
            "practices",
            "01-links",
            "references:\n  - kind: contest\n    url: https://example.com/contest\n",
        )
        course = self.course(["lectures/01-topic"])
        course["weeks"].append(
            {
                "slug": "second",
                "number": 1,
                "title": "Следующая",
                "description": "Описание",
                "materials": ["practices/01-links"],
            }
        )
        (self.root / "course.json").write_text(json.dumps(course), encoding="utf-8")
        entries = site.discover_sessions()
        manifest = site.build_manifest(entries, site.load_course(self.root, entries))
        stale = self.output / "weeks/stale/index.html"
        stale.parent.mkdir(parents=True)
        stale.touch()
        site.publish_pages(Path(__file__).parents[2], self.output, manifest)
        self.assertFalse(stale.exists())
        first = (self.output / "weeks/topic/index.html").read_text()
        second = (self.output / "weeks/second/index.html").read_text()
        self.assertIn('href="../second/" rel="next"', first)
        self.assertNotIn('rel="prev"', first)
        self.assertIn('href="../topic/" rel="prev"', second)
        self.assertNotIn('rel="next"', second)
        self.assertIn('href="https://example.com/contest"', second)
        self.assertNotIn('href="../../pdfs/', second)

    def test_notebook_preview_target_and_pdf_priority(self):
        self.session(
            "practices",
            "01-files",
            "materials:\n  - path: materials/a.ipynb\n  - path: materials/b.ipynb\n",
        )
        out = self.output / "materials/practices/01-files"
        out.mkdir(parents=True)
        for name in ("a.ipynb", "b.ipynb"):
            (out / name).touch()
        preview = self.output / "thumbs/practices/01-files/a.ipynb.svg"
        preview.parent.mkdir(parents=True)
        preview.touch()
        entry = self.manifest()["materials"][0]
        self.assertEqual(entry["thumb"], "thumbs/practices/01-files/a.ipynb.svg")
        self.assertEqual(entry["thumb_href"], "materials/practices/01-files/a.ipynb")
        (out / "a.html").touch()
        entry = self.manifest()["materials"][0]
        self.assertEqual(entry["thumb_href"], "materials/practices/01-files/a.html")
        pdf = self.output / "pdfs/practices/01-files.pdf"
        pdf.parent.mkdir(parents=True)
        pdf.touch()
        thumb = self.output / "thumbs/practices/01-files.png"
        thumb.touch()
        entry = self.manifest()["materials"][0]
        self.assertEqual(entry["thumb"], "thumbs/practices/01-files.png")
        self.assertEqual(entry["thumb_href"], "pdfs/practices/01-files.pdf")

    def test_assignment_notebook_preview_and_pdf_priority(self):
        self.session(
            "assignments",
            "04-knn",
            "assignment_type: coding\nmaterials:\n  - path: materials/task.ipynb\n",
        )
        out = self.output / "materials/assignments/04-knn"
        out.mkdir(parents=True)
        (out / "task.ipynb").touch()
        preview = self.output / "thumbs/assignments/04-knn/task.ipynb.svg"
        preview.parent.mkdir(parents=True)
        preview.touch()

        entry = self.manifest()["materials"][0]
        self.assertEqual(entry["kind"], "assignment")
        self.assertEqual(entry["thumb"], "thumbs/assignments/04-knn/task.ipynb.svg")
        self.assertEqual(entry["thumb_href"], "materials/assignments/04-knn/task.ipynb")

        pdf = self.output / "pdfs/assignments/04-knn.pdf"
        pdf.parent.mkdir(parents=True)
        pdf.touch()
        pdf_thumb = self.output / "thumbs/assignments/04-knn.png"
        pdf_thumb.parent.mkdir(parents=True, exist_ok=True)
        pdf_thumb.touch()
        entry = self.manifest()["materials"][0]
        self.assertEqual(entry["thumb"], "thumbs/assignments/04-knn.png")
        self.assertEqual(entry["thumb_href"], "pdfs/assignments/04-knn.pdf")


if __name__ == "__main__":
    unittest.main()
