"""Проверка миниатюр из исходных ячеек ноутбука."""

import contextlib
import io
import json
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))
from material_preview import build_preview, notebook_content, render_preview


class PreviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.session = self.root / "course/00-topic/practice"
        self.session.mkdir(parents=True)
        self.output = self.root / "_site"

    def notebook(self, name, cells):
        path = self.session / name
        path.write_text(json.dumps({"cells": cells}), encoding="utf-8")
        return path

    def meta(self, names):
        (self.session / "material.yml").write_text(
            "materials:\n" + "".join(f"  - path: {name}\n" for name in names)
        )

    def test_extract_wrap_and_escape(self):
        path = self.notebook(
            "a.ipynb",
            [
                {
                    "cell_type": "markdown",
                    "source": ["# Заголовок & пример\n\n", "Короткое **описание**."],
                },
                {"cell_type": "code", "source": ""},
                {
                    "cell_type": "code",
                    "source": 'print("<&>")\n' + "x" * 200 + "\n" + "line\n" * 8,
                },
                {"cell_type": "code", "source": "Не показывать"},
            ],
        )
        content = notebook_content(path)
        self.assertEqual(content[0][0], "code")
        self.assertNotIn("Заголовок", render_preview(content))
        self.assertEqual(content[1][0], "code")
        svg = render_preview(content)
        ET.fromstring(svg)
        self.assertIn("&lt;&amp;&gt;", svg)
        self.assertIn("…", svg)
        self.assertNotIn("НОУТБУК ПРАКТИКИ", svg)
        self.assertIn('aria-label="Python"', svg)
        self.assertNotIn("x" * 100, svg)
        self.assertEqual(ET.fromstring(svg).get("viewBox"), "0 0 640 360")

    def test_first_available_and_pdf_priority(self):
        self.notebook("a.ipynb", [{"cell_type": "code", "source": "first"}])
        self.notebook("b.ipynb", [{"cell_type": "code", "source": "second"}])
        self.meta(["missing.ipynb", "a.ipynb", "b.ipynb"])
        build_preview(self.session, self.output)
        preview = self.output / "thumbs/00-topic/practice/a.ipynb.svg"
        self.assertIn("first", preview.read_text())
        self.assertFalse((preview.parent / "b.ipynb.svg").exists())
        pdf = self.output / "pdfs/00-topic/practice.pdf"
        pdf.parent.mkdir(parents=True)
        pdf.touch()
        build_preview(self.session, self.output)
        self.assertFalse(preview.exists())

    def test_empty_invalid_and_removed_notebook_clear_previous_preview(self):
        self.meta(["a.ipynb"])
        path = self.notebook("a.ipynb", [{"cell_type": "code", "source": "hello"}])
        build_preview(self.session, self.output)
        preview = self.output / "thumbs/00-topic/practice/a.ipynb.svg"
        path.write_text('{"cells": []}')
        self.assertIsNone(notebook_content(path))
        build_preview(self.session, self.output)
        self.assertFalse(preview.exists())
        path.write_text("broken")
        with contextlib.redirect_stderr(io.StringIO()) as errors:
            build_preview(self.session, self.output)
        self.assertIn("Не удалось создать превью", errors.getvalue())
        path.unlink()
        build_preview(self.session, self.output)
        self.assertFalse(preview.exists())

    def test_markdown_only_notebook_has_no_preview(self):
        path = self.notebook(
            "text.ipynb", [{"cell_type": "markdown", "source": "# Только текст"}]
        )
        self.assertIsNone(notebook_content(path))

    def test_assignment_notebook_preview_uses_same_code_fragment(self):
        assignment = self.root / "course/00-topic/assignment"
        assignment.mkdir(parents=True)
        (assignment / "material.yml").write_text(
            "assignment_type: coding\nmaterials:\n  - path: materials/task.ipynb\n",
            encoding="utf-8",
        )
        materials = assignment / "materials"
        materials.mkdir()
        notebook = materials / "task.ipynb"
        notebook.write_text(
            json.dumps(
                {
                    "cells": [
                        {"cell_type": "markdown", "source": "# Assignment"},
                        {"cell_type": "code", "source": "answer = 42"},
                        {
                            "cell_type": "code",
                            "source": "print(1)",
                            "outputs": [{"output_type": "stream", "text": "cell output"}],
                        },
                    ]
                }
            ),
            encoding="utf-8",
        )
        build_preview(assignment, self.output)
        preview = self.output / "thumbs/00-topic/assignment/task.ipynb.svg"
        svg = preview.read_text(encoding="utf-8")
        self.assertIn("answer =", svg)
        self.assertIn(">42</tspan>", svg)
        self.assertNotIn("cell output", svg)

    def test_pdf_preview_takes_priority_over_notebook(self):
        import subprocess
        from unittest.mock import patch

        self.meta(["a.ipynb"])
        self.notebook("a.ipynb", [{"cell_type": "code", "source": "print(1)"}])
        pdf = self.output / "pdfs/00-topic/practice.pdf"
        pdf.parent.mkdir(parents=True)
        pdf.touch()
        (self.output / "thumbs/00-topic/practice").mkdir(parents=True)
        (self.output / "thumbs/00-topic/practice/stale.svg").touch()

        def render_pdf(command, **kwargs):
            Path(command[-1] + ".png").write_bytes(b"png")
            return subprocess.CompletedProcess(command, 0, "", "")

        with patch("material_preview.shutil.which", return_value="pdftoppm"), patch(
            "material_preview.subprocess.run", side_effect=render_pdf
        ):
            build_preview(self.session, self.output)
        self.assertTrue((self.output / "thumbs/00-topic/practice.png").is_file())
        self.assertFalse((self.output / "thumbs/00-topic/practice/stale.svg").exists())
        self.assertFalse((self.output / "thumbs/00-topic/practice/a.ipynb.svg").exists())

    def test_square_icon_and_code_layout(self):
        content = [
            ("code", 'import numpy as np\nprint("hello")'),
            ("code", "x = 12\n" * 30),
        ]
        root = ET.fromstring(render_preview(content))
        ns = {"s": "http://www.w3.org/2000/svg"}
        badge = root.find('s:rect[@x="508"]', ns)
        self.assertEqual(badge.get("width"), badge.get("height"))
        icon = root.find('s:image[@aria-label="Python"]', ns)
        self.assertIsNotNone(icon)
        self.assertEqual(int(badge.get("x")) + int(badge.get("width")), 640)
        self.assertEqual(int(badge.get("y")) + int(badge.get("height")), 360)
        for axis, size in [("x", "width"), ("y", "height")]:
            self.assertEqual(
                int(icon.get(axis)) + int(icon.get(size)) / 2,
                int(badge.get(axis)) + int(badge.get(size)) / 2,
            )
        texts = root.findall(".//s:text", ns)
        self.assertTrue(all(int(text.get("y")) <= 326 for text in texts))
        self.assertTrue(root.findall(".//s:tspan", ns))
