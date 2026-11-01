"""Semantic publication contracts using temporary, synthetic teaching material."""
from copy import deepcopy
import json
from pathlib import Path
import shutil
import subprocess
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from handbook_blocks import parse,markdown,pdf_questions,plain
from handbook_notebooks import render_notebook,update_markdown_cells
from repo_paths import REPO_ROOT

SOURCE='''Intro.

::::: {.self-check}

:::: {.question #compare correct="B"}

Compare $x+1$ with **two** values.

::: {.choices}

A. First.
B. Second with $x$.
C. Third.
D. Fourth.

:::

::: {.hint}

Hint with `code`.

A second paragraph.

:::

::: {.solution}

**B.** A reason, 50% & more.

```python
print("::: {.question}")
```

:::

::::

:::::

::: {.callout type="note" title="A & B"}

Extra $x$ explanation.

:::
'''

class SemanticBlocksTests(unittest.TestCase):
    def test_structure_ids_and_text_survive_adapters(self):
        tree=parse(SOURCE,'synthetic');q=tree[1]['children'][1]
        self.assertEqual(q['attrs']['id'],'compare')
        self.assertEqual(q['number'],1)
        self.assertEqual(next(c for c in q['children'] if c['kind']=='choices')['items'][1],'Second with $x$.')
        out=markdown(tree,'notebook')
        self.assertLess(out.index('Extra $x$'),out.index('## Подсказки и решения'))
        self.assertIn('A second paragraph.',out)
        self.assertIn('print("::: {.question}")',out)
        self.assertNotIn('correct=',out)

    def test_invalid_blocks_report_material_and_question(self):
        for bad in [SOURCE.replace('correct="B"','correct="E"'),SOURCE.replace('B. Second','C. Second'),
                    SOURCE.replace('#compare','#bad_id'),SOURCE.replace('Hint with `code`.\n\nA second paragraph.','')]:
            with self.subTest(source=bad),self.assertRaisesRegex(ValueError,'fixture: вопрос'):
                parse(bad,'fixture')
        with self.assertRaisesRegex(ValueError,'незакрытый'):
            parse(SOURCE.replace('\n:::::\n','\n'),'fixture')
        duplicate=SOURCE.replace('\n:::::\n', '\n'+SOURCE[SOURCE.index(':::: {.question'):SOURCE.index('\n:::::\n')]+'\n:::::\n',1)
        with self.assertRaisesRegex(ValueError,'повторяется'):
            parse(duplicate,'fixture')

    def test_unrelated_details_numbered_headings_and_code_are_untouched(self):
        value='### 7. Ordinary heading\n\n<details><summary>Help</summary>Text</details>\n\n```md\n::: {.callout}\n```\n'
        self.assertEqual(markdown(parse(value)),value)

    def test_notebook_preserves_executed_cells_metadata_and_attachments(self):
        expected=render_notebook('Fixture',SOURCE)
        original=deepcopy(expected)
        original['metadata']['custom']='keep'
        for c in original['cells']:
            c['metadata']['custom']='cell'
            if c['cell_type']=='code':
                c.update(execution_count=9,outputs=[{'output_type':'stream','name':'stdout','text':['result']}])
        before=deepcopy(original)
        updated=update_markdown_cells(original,expected)
        self.assertEqual(original,before)
        self.assertEqual(updated['metadata']['custom'],'keep')
        self.assertEqual([c for c in updated['cells'] if c['cell_type']=='code'],[c for c in original['cells'] if c['cell_type']=='code'])
        self.assertEqual(update_markdown_cells(updated,expected),updated)

    @unittest.skipUnless(shutil.which('pandoc'),'Pandoc required')
    def test_pdf_extraction_preserves_feedback_and_individual_page_labels(self):
        ast=json.loads(subprocess.check_output(['pandoc','-f','markdown','-t','json'],input=markdown(parse(SOURCE)),text=True))
        original=deepcopy(ast['blocks']);questions,answers=pdf_questions(ast['blocks'],'book/chapter/lesson')
        self.assertEqual(original,ast['blocks'])
        self.assertIn('OrderedList',json.dumps(questions))
        q=json.dumps(questions,ensure_ascii=False);a=json.dumps(answers,ensure_ascii=False)
        self.assertNotIn('A second paragraph.',q)
        self.assertIn('paragraph.',a)
        self.assertIn('--compare--hint',q)
        self.assertIn('--compare--solution',q)
        self.assertIn('К вопросу',a)
        self.assertNotIn('Header',json.dumps(answers))

    @unittest.skipUnless(shutil.which('node'),'Node required')
    def test_site_semantics_noscript_fallback_and_escaping(self):
        request=[{'name':'fixture','source':SOURCE,'blocks':parse(SOURCE)}]
        rendered=json.loads(subprocess.check_output(['node',str(REPO_ROOT/'utils/site/render-handbook.mjs')],input=json.dumps(request),text=True))[0]
        html=rendered['html']
        self.assertEqual(html.count('type="radio"'),4)
        self.assertIn('<fieldset aria-describedby=',html)
        self.assertIn('role="status"',html)
        self.assertIn('class="quiz-check" hidden disabled',html)
        self.assertIn('<details class="quiz-solution">',html)
        self.assertIn('A &amp; B',html)
        self.assertIn('aria-hidden="true"',html)
        self.assertNotIn('self-check}',html)

    @unittest.skipUnless(__import__('os').environ.get('PDF_RENDER_TESTS')=='1','Real TeX checks enabled with PDF_RENDER_TESTS=1')
    def test_real_pdf_links_and_long_callout_in_both_profiles(self):
        import os,tempfile,pymupdf
        tree=parse(SOURCE)
        ast=json.loads(subprocess.check_output(['pandoc','-f','markdown','-t','json'],input=markdown(tree),text=True))
        prompt,answers=pdf_questions(ast['blocks'],'fixture/chapter/lesson')
        # A long box must split while preserving every paragraph.
        long_source='::: {.callout type="warning"}\n\n'+'\n\n'.join(f'Paragraph {i}: '+('Long readable explanation. '*12) for i in range(18))+'\n\n:::\n'
        long_ast=json.loads(subprocess.check_output(['pandoc','-f','markdown','-t','json'],input=markdown(parse(long_source)),text=True))
        ast['blocks']=prompt+[{'t':'RawBlock','c':['latex',r'\clearpage']}]+answers+long_ast['blocks']
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp)
            for package in ('academichandbook','belarustextbook'):
                header=folder/'header.tex'
                header.write_text('\\usepackage{fvextra}\n\\usepackage{handbookfonts,'+package+'}\n\\AtBeginDocument{\\pagestyle{empty}}\n')
                target=folder/(package+'.pdf')
                env=dict(os.environ,TEXINPUTS=str(REPO_ROOT/'utils/latex/tex/latex')+'//'+os.pathsep+os.environ.get('TEXINPUTS',''))
                result=subprocess.run(['pandoc','-f','json','--pdf-engine=pdflatex','--include-in-header',str(header),
                                '--lua-filter',str(REPO_ROOT/'utils/pdf/keep-short-code.lua'),'-V','fontenc:T2A',
                                '-V','classoption:twoside',
                                '-o',str(target)],input=json.dumps(ast),text=True,env=env,capture_output=True)
                self.assertEqual(result.returncode,0,result.stderr[-3000:])
                with pymupdf.open(target) as document:
                    text='\n'.join(p.get_text() for p in document)
                    self.assertIn('Paragraph 17:',text)
                    self.assertIn('A second paragraph.',text)
                    self.assertNotIn('??',text)
                    self.assertGreater(len(document),2)
                    self.assertTrue(any(p.get_links() for p in document))
                    feedback=next(i for i,p in enumerate(document) if 'A second paragraph.' in p.get_text())
                    self.assertGreater(feedback,0)
                    self.assertNotIn('A second paragraph.',document[0].get_text())

    @unittest.skipUnless(shutil.which('pandoc'),'Pandoc required')
    def test_nested_figures_and_tables_keep_captions_when_feedback_moves(self):
        from handbook_pdf import format_objects,printable,require_object_captions,walk
        source=SOURCE.replace('A second paragraph.','A second paragraph.\n\n![Accessible explanation](diagram.svg)\n\n*Рисунок 7 — A diagram*\n\n*Таблица 9 — Values*\n\n| Label | Value |\n| --- | ---: |\n| x | 2 |')
        ast=json.loads(subprocess.check_output(['pandoc','-f','markdown-implicit_figures','-t','json'],input=markdown(parse(source)),text=True))
        ast=format_objects(printable(ast))
        require_object_captions(ast,'fixture')
        prompt,feedback=pdf_questions(ast['blocks'],'fixture')
        self.assertFalse(any(n.get('t')=='Image' for n in walk(prompt)))
        self.assertEqual(sum(n.get('t')=='Image' for n in walk(feedback)),1)
        self.assertEqual(sum(n.get('t')=='Table' for n in walk(feedback)),1)
        self.assertTrue(any(n.get('t')=='Div' and 'handbook-figure' in n['c'][0][1] for n in walk(feedback)))

    def test_manual_notebook_updates_only_managed_quiz_and_removes_it_when_deleted(self):
        from handbook_notebooks import update_semantic_cell
        original={'cells':[{'cell_type':'markdown','id':'manual','metadata':{'x':1},'source':['Manual text.']},
                           {'cell_type':'code','id':'run','source':['print(1)'],'execution_count':8,'outputs':[]}],
                  'metadata':{'custom':True}}
        updated=update_semantic_cell(original,SOURCE)
        self.assertEqual(updated['cells'][:2],original['cells'])
        self.assertEqual(updated['metadata'],original['metadata'])
        self.assertEqual(update_semantic_cell(updated,SOURCE),updated)
        self.assertEqual(update_semantic_cell(updated,'No quiz.'),original)
        changed=update_semantic_cell(updated,SOURCE.replace('A second paragraph.','Changed hint.'))
        self.assertIn('Changed hint.',''.join(changed['cells'][-1]['source']))

    @unittest.skipUnless(shutil.which('pandoc'),'Pandoc required')
    def test_quiz_spacing_counts_characters_instead_of_utf8_bytes(self):
        def reserve(character):
            ast={'pandoc-api-version':[1,23,1],'meta':{},'blocks':[{'t':'Div','c':[['',['handbook-quiz-prompt'],[]],[{'t':'Para','c':[{'t':'Str','c':character*60}]}]]}]}
            return subprocess.check_output(['pandoc','-f','json','-t','latex','--lua-filter',str(REPO_ROOT/'utils/pdf/keep-short-code.lua')],input=json.dumps(ast),text=True).splitlines()[0]
        self.assertEqual(reserve('a'),reserve('я'))
