"""Validated semantic Markdown blocks shared by handbook publication adapters."""
from __future__ import annotations
import re
import json
import shlex

KINDS = {'self-check', 'question', 'choices', 'hint', 'solution', 'callout'}
TITLES = {'important': 'Важно', 'warning': 'Предупреждение', 'note': 'Примечание', 'tip': 'Совет'}
OPEN = re.compile(r'^(:{3,})\s*\{([^}]+)\}\s*$')


def parse(source, material='material'):
    lines = source.splitlines(keepends=True)
    def read(start, closing=None):
        result, text, code = [], [], None
        def flush():
            if text:
                result.append({'kind': 'text', 'text': ''.join(text)})
                text.clear()
        index = start
        while index < len(lines):
            line = lines[index]
            fence = re.match(r'^\s{0,3}(`{3,}|~{3,})', line)
            if fence:
                marker = fence[1]
                if code is None:
                    code = marker
                elif marker[0] == code[0] and len(marker) >= len(code):
                    code = None
            if code is None and closing and re.fullmatch(r'\s*:{' + str(closing) + r'}\s*', line):
                flush()
                return result, index + 1
            match = OPEN.match(line.rstrip('\n')) if code is None else None
            if match:
                try:
                    parts = shlex.split(match[2])
                except ValueError as error:
                    raise ValueError(f'{material}:{index + 1}: {error}') from error
                classes = [p[1:] for p in parts if p.startswith('.')]
                semantic = [p for p in classes if p in KINDS]
                if semantic:
                    flush()
                    if len(semantic) != 1:
                        raise ValueError(f'{material}:{index + 1}: неоднозначный тип блока')
                    attrs = dict(p.split('=', 1) for p in parts if '=' in p)
                    ids = [p[1:] for p in parts if p.startswith('#')]
                    if ids:
                        attrs['id'] = ids[0]
                    children, end = read(index + 1, len(match[1]))
                    result.append({'kind': semantic[0], 'attrs': attrs, 'children': children})
                    index = end
                    continue
            text.append(line)
            index += 1
        if closing:
            raise ValueError(f'{material}: незакрытый структурный блок')
        flush()
        return result, index
    tree, _ = read(0)
    seen, number = set(), 0
    def validate(nodes, parent=None, question=None):
        nonlocal number
        for node in nodes:
            kind = node['kind']
            if kind == 'text':
                continue
            attrs, children = node['attrs'], node['children']
            context = f'{material}: вопрос {attrs.get("id") or question or "?"}'
            def fail(message):
                raise ValueError(context + ': ' + message)
            allowed = {'self-check': {'question'}, 'question': {'choices', 'hint', 'solution'},
                       'choices': set(), 'hint': {'callout'}, 'solution': {'callout'}, 'callout': {'callout'}}
            if parent is not None and kind not in allowed[parent]:
                fail(f'блок {kind} недопустим внутри {parent}')
            if parent is None and kind not in {'self-check', 'callout'}:
                fail(f'блок {kind} вне своего контейнера')
            if kind == 'question':
                qid = attrs.get('id', '')
                if not re.fullmatch(r'[a-z][a-z0-9-]*', qid) or qid in seen:
                    fail('ID отсутствует, повторяется или имеет неверный формат')
                seen.add(qid)
                number += 1
                node['number'] = number
                required = ['choices', 'hint', 'solution']
                typed = [c['kind'] for c in children if c['kind'] != 'text']
                if typed != required:
                    fail('ожидаются choices, hint, solution, по одному и в этом порядке')
                prompt = ''.join(c['text'] for c in children[:next(i for i,c in enumerate(children) if c['kind']=='choices')] if c['kind']=='text').strip()
                if not prompt:
                    fail('пустое условие')
                for child in children:
                    if child['kind'] in {'hint', 'solution'} and not plain(child).strip():
                        fail('пустой блок ' + child['kind'])
                choices = next(c for c in children if c['kind']=='choices')
                choices['items'] = choice_items(plain(choices), context)
                if attrs.get('correct', '') not in ('A', 'B', 'C', 'D'):
                    fail('correct должен указывать вариант A–D')
            if kind == 'callout' and attrs.get('type') not in TITLES:
                fail('неизвестный type вставки')
            if kind == 'self-check' and not any(c['kind']=='question' for c in children):
                fail('пустая самопроверка')
            validate(children, kind, attrs.get("id", question))
    validate(tree)
    return tree


def plain(node):
    return node.get('text', '') if node['kind']=='text' else ''.join(plain(c) for c in node['children'])


def choice_items(text, context):
    matches = list(re.finditer(r'^([A-D])\.\s+', text, re.M))
    if [m[1] for m in matches] != list('ABCD') or text[:matches[0].start()].strip():
        raise ValueError(context + ': ожидаются четыре варианта A–D')
    result = []
    for i, match in enumerate(matches):
        value = text[match.end():matches[i+1].start() if i+1<len(matches) else len(text)].strip()
        value = re.sub(r'^ {3}', '', value, flags=re.M)
        if not value:
            raise ValueError(context + ': пустой вариант ' + match[1])
        result.append(value)
    return result


def markdown(tree, target='pdf'):
    """Native fenced Divs for Pandoc; portable Markdown for notebooks."""
    answers = []
    def render(nodes, depth=0):
        result = []
        for node in nodes:
            kind = node['kind']
            if kind == 'text':
                result.append(node['text'])
                continue
            attrs = node['attrs']
            if target == 'notebook':
                if kind == 'question':
                    children = node['children']; number = node['number']
                    prompt = ''.join(render([c], depth+1) for c in children if c['kind']=='text').strip()
                    choices = next(c for c in children if c['kind']=='choices')
                    result.append(f'\n\n### {number}. {prompt}\n\n' + '\n\n'.join(f'{letter}. {value}' for letter,value in zip('ABCD',choices['items'])) + '\n\n')
                    hint = next(c for c in children if c['kind']=='hint'); solution = next(c for c in children if c['kind']=='solution')
                    answers.append(f'### Вопрос {number}\n\n**Подсказка**\n\n{render(hint["children"])}\n\n**Решение**\n\n{render(solution["children"])}\n\n')
                elif kind == 'callout':
                    title = attrs.get('title', TITLES[attrs['type']])
                    body = render(node['children']).strip()
                    result.append('\n\n' + '\n'.join('> ' + line for line in (f'**{title}**\n\n' + body).splitlines()) + '\n\n')
                else:
                    result.append(render(node['children'],depth+1))
            else:
                def nesting(n):
                    return 0 if n['kind']=='text' else 1 + max((nesting(c) for c in n['children']), default=0)
                fence = ':' * (3 + nesting(node))
                options = [f'.handbook-{kind}']
                for key,value in attrs.items():
                    if key=='id':
                        options.append('#'+value)
                    else:
                        options.append(key+'='+json.dumps(value,ensure_ascii=False))
                if kind=='question':
                    options.append('number="'+str(node['number'])+'"')
                body = ('\n\n'.join(letter + '.  ' + value.replace('\n','\n    ') for letter,value in zip('ABCD',node['items']))
                        if kind == 'choices' else render(node['children'],depth+1))
                result.append('\n\n'+fence+' {'+' '.join(options)+'}\n\n'+body+'\n\n'+fence+'\n\n')
        return ''.join(result)
    body=render(tree)
    return body + ('\n\n## Подсказки и решения\n\n'+''.join(answers) if answers else '')


def pdf_questions(blocks, material):
    """Replace explicit questions with prompts; return independently placeable feedback."""
    from copy import deepcopy
    result, answers = [], []
    prefix = material.replace('/', '--') + '--quiz--'
    def raw(text): return {'t':'RawBlock','c':['latex',text]}
    def para(text): return {'t':'Para','c':[{'t':'Strong','c':[{'t':'Str','c':text}]}]}
    def visit(nodes):
        out=[]
        for node in nodes:
            if node.get('t')=='Div' and 'handbook-question' in node['c'][0][1]:
                attr,children=node['c']; attrs=dict(attr[2]); number=attrs['number']
                key=prefix+attr[0]
                prompt=[]; groups={}
                for child in children:
                    if child.get('t')=='Div' and any('handbook-'+k in child['c'][0][1] for k in ('choices','hint','solution')):
                        kind=next(k for k in ('choices','hint','solution') if 'handbook-'+k in child['c'][0][1]); groups[kind]=child['c'][1]
                    else: prompt.append(deepcopy(child))
                first=next((p for p in prompt if p.get('t')=='Para'),None)
                if first:
                    first['c']=[{'t':'Strong','c':[{'t':'Str','c':number+'.'}]},{'t':'Space'},*first['c']]
                prompt.extend(deepcopy(groups['choices']))
                prompt.insert(0,raw(r'\phantomsection\label{'+key+'}'))
                out.append({'t':'Div','c':[['',['handbook-quiz-prompt'],[]],prompt]})
                out.append(raw(r'\par\smallskip\noindent\textit{Подсказка — с.~\pageref{'+key+'--hint'+r'}; решение — с.~\pageref{'+key+'--solution'+r'}.}\par'))
                answers.extend([raw(r'\par\addvspace{12pt}\Needspace{6\baselineskip}'),para('Вопрос '+number), raw(r'\noindent\hyperref['+key+r']{К вопросу на с.~\pageref*{'+key+r'}}.\par'),
                                raw(r'\Needspace{4\baselineskip}\phantomsection\label{'+key+'--hint}'),para('Подсказка'),*deepcopy(groups['hint']),
                                raw(r'\Needspace{4\baselineskip}\phantomsection\label{'+key+'--solution}'),para('Решение'),*deepcopy(groups['solution'])])
            elif node.get('t')=='Div':
                node=deepcopy(node);node['c'][1]=visit(node['c'][1]);out.append(node)
            else: out.append(node)
        return out
    result=visit(blocks)
    return result,answers
