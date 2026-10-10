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
        entry = site.build_manifest(site.discover_sessions())["materials"][0]
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
        manifest = site.build_manifest(site.discover_sessions())
        encoded = json.dumps(manifest, ensure_ascii=False)
        self.assertEqual(json.loads(encoded), manifest)
        self.assertEqual(manifest["version"], 1)
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
        files = site.build_manifest(site.discover_sessions())["materials"][0][
            "materials"
        ]
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
        for name in ("index.html", "favicon.svg"):
            (source / name).write_text("оболочка", encoding="utf-8")
        with patch.multiple(
            site, REPO_ROOT=self.root, FONTS_SRC=fonts, FONTS_DEST=self.output / "fonts"
        ):
            site.main()
        data = json.loads((self.output / "materials.json").read_text())
        self.assertEqual(data["version"], 1)
        self.assertEqual(data["materials"][0]["id"], "lectures/01-topic")
        self.assertTrue((self.output / "fonts/test.woff2").is_file())
        self.assertEqual((self.output / "index.html").read_text(), "оболочка")

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
        entry = site.build_manifest(site.discover_sessions())["materials"][0]
        self.assertEqual(entry["thumb"], "thumbs/practices/01-files/a.ipynb.svg")
        self.assertEqual(entry["thumb_href"], "materials/practices/01-files/a.ipynb")
        (out / "a.html").touch()
        entry = site.build_manifest(site.discover_sessions())["materials"][0]
        self.assertEqual(entry["thumb_href"], "materials/practices/01-files/a.html")
        pdf = self.output / "pdfs/practices/01-files.pdf"
        pdf.parent.mkdir(parents=True)
        pdf.touch()
        thumb = self.output / "thumbs/practices/01-files.png"
        thumb.touch()
        entry = site.build_manifest(site.discover_sessions())["materials"][0]
        self.assertEqual(entry["thumb"], "thumbs/practices/01-files.png")
        self.assertEqual(entry["thumb_href"], "pdfs/practices/01-files.pdf")


if __name__ == "__main__":
    unittest.main()
