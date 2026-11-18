"""Каталог контестов проверяется на синтетических материалах."""
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from contest_site import load_contests, publish_contests, validate_links


class ContestSiteTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        contests = self.root / "contests"
        task = contests / "2028" / "sample" / "task"
        task.mkdir(parents=True)
        (contests / "README.md").write_text("# Fixture catalogue\n\nFixture introduction.\n")
        (contests / "contests.yml").write_text("title: Fixture contests\ndescription: Fixture.\nyears:\n  - slug: '2028'\n")
        (contests / "2028/meta.yml").write_text(
            "slug: '2028'\ntitle: Fixture year\ndescription: Year description.\nstages:\n  - sample\n")
        (contests / "2028/content.md").write_text("# Fixture year\n")
        (contests / "2028/sample/meta.yml").write_text(
            "slug: sample\ntitle: Fixture stage\ndescription: Stage description.\n"
            "date: '2028-01-01'\ncontest_url: https://example.com/contest\n"
            "leaderboard_url: https://example.com/leaderboard\ntasks:\n  - task\n")
        (contests / "2028/sample/content.md").write_text("# Fixture stage\n")
        (task / "meta.yml").write_text(
            "slug: task\ntitle: Fixture task\ndescription: Task description.\n"
            "kind: math\noriginal: https://example.com/task\n")
        (task / "statement.md").write_text("### Input data\n\nFull statement with $x^2$.\n")
        (task / "analysis.md").write_text("### Solution idea\n\nSolution.\n")
        (self.root / "utils/site").mkdir(parents=True)
        for name in ("index.html", "render-handbook.mjs"):
            shutil.copyfile(Path(__file__).parents[3] / "utils/site" / name,
                            self.root / "utils/site" / name)
        (self.root / "utils/site/node_modules").symlink_to(
            Path(__file__).parents[3] / "utils/site/node_modules", target_is_directory=True
        )
        self.output = self.root / "_site"
        for path in ("index.html", "materials/index.html", "handbooks/index.html"):
            target = self.output / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("<html></html>")
        for path in ("assets/site.css", "assets/materials.js", "favicon.svg",
                     "assets/fontawesome/github.svg", "assets/fontawesome/instagram.svg",
                     "assets/fontawesome/tiktok.svg", "assets/fontawesome/telegram.svg",
                     "assets/fontawesome/creative-commons.svg", "license/index.html"):
            target = self.output / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.touch()

    def test_hierarchical_routes_pages_navigation_and_cleanup(self):
        stale = self.output / "contests/stale/index.html"
        stale.parent.mkdir(parents=True)
        stale.touch()
        catalog = load_contests(self.root)
        self.assertEqual(len(catalog["years"]), 1)
        self.assertEqual(len(catalog["years"][0]["stages"][0]["tasks"]), 1)

        old_pdf = self.output / "contests/2028/sample/task/statement.pdf"
        old_pdf.parent.mkdir(parents=True)
        old_pdf.touch()
        publish_contests(self.root, self.output, [])
        self.assertFalse(old_pdf.exists())

        self.assertFalse(stale.exists())
        pages = {
            "catalog": self.output / "contests/index.html",
            "year": self.output / "contests/2028/index.html",
            "stage": self.output / "contests/2028/sample/index.html",
            "task": self.output / "contests/2028/sample/task/index.html",
        }
        for path in pages.values():
            self.assertTrue(path.is_file())
        self.assertIn('href="2028/"', pages["catalog"].read_text())
        self.assertIn('href="sample/"', pages["year"].read_text())
        stage_html = pages["stage"].read_text()
        self.assertIn('href="task/"', stage_html)
        self.assertIn('href="statements.pdf"', stage_html)
        self.assertIn('href="debrief.pdf"', stage_html)
        task_html = pages["task"].read_text()
        self.assertIn('href="#statement"', task_html)
        self.assertIn('href="#analysis"', task_html)
        self.assertIn('id="analysis"', task_html)
        self.assertNotIn('statement.pdf', task_html)
        self.assertNotIn('statement.pdf', stage_html)
        self.assertIn('class="handbook-navigation"', task_html)
        self.assertIn('aria-current="page">Fixture task</a>', task_html)
        self.assertIn('assets/katex/katex.min.css', task_html)
        self.assertEqual(task_html.count('class="katex-mathml"'), 1)
        self.assertNotIn('class="handbook-lessons"', pages["year"].read_text())
        self.assertTrue((self.output / "assets/katex/katex.min.css").is_file())
        self.assertIn('href="../../../../contests/"', task_html)
        validate_links(self.output)

    def test_repeated_year_and_unsafe_source_paths_are_rejected(self):
        registry = self.root / "contests/contests.yml"
        registry.write_text("title: Fixture\ndescription: Fixture.\nyears:\n  - slug: '2028'\n  - slug: '2028'\n")
        with self.assertRaises(ValueError):
            load_contests(self.root)

        registry.write_text("title: Fixture\ndescription: Fixture.\nyears:\n  - slug: '../outside'\n")
        with self.assertRaises(ValueError):
            load_contests(self.root)

    def test_task_metadata_must_match_folder_slug(self):
        path = self.root / "contests/2028/sample/task/meta.yml"
        data = yaml.safe_load(path.read_text())
        data["slug"] = "different"
        path.write_text(yaml.safe_dump(data, allow_unicode=True))
        with self.assertRaises(ValueError):
            load_contests(self.root)


if __name__ == "__main__":
    unittest.main()
