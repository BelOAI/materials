"""Авторские рисунки учебника: python3 utils/scripts/handbook_figures.py [--output DIR]."""
from __future__ import annotations

import argparse
from pathlib import Path
import xml.etree.ElementTree as ET

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

from repo_paths import REPO_ROOT as ROOT
BLUE, ORANGE, GREEN, GRAY = '#2563eb', '#b45309', '#15803d', '#64748b'
SVG = 'http://www.w3.org/2000/svg'


def generate(output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    # Сохраняем текст SVG; запасной шрифт работает и без DejaVu на телефоне.
    with plt.rc_context({'font.family': ['DejaVu Sans', 'sans-serif'],
                         'font.size': 13, 'axes.titlesize': 14,
                         'xtick.labelsize': 12, 'ytick.labelsize': 12,
                         'svg.fonttype': 'none', 'svg.hashsalt': 'beloai-handbook'}):
        def save(fig, name, title, description):
            path = output / (name + '.svg')
            fig.savefig(path, metadata={'Date': None, 'Creator': 'Авторы BelOAI',
                                        'Title': title, 'Description': description})
            plt.close(fig)
            # Название и описание доступны и при отдельном открытии SVG.
            tree = ET.parse(path)
            root = tree.getroot()
            root.set('role', 'img')
            root.set('aria-labelledby', name + '-title ' + name + '-description')
            title_node = root.find('{' + SVG + '}title')
            if title_node is None:
                title_node = ET.SubElement(root, '{' + SVG + '}title')
            title_node.set('id', name + '-title')
            title_node.text = title
            desc = ET.Element('{' + SVG + '}desc', {'id': name + '-description'})
            desc.text = description
            root.insert(1, desc)
            ET.register_namespace('', SVG)
            ET.register_namespace('xlink', 'http://www.w3.org/1999/xlink')
            tree.write(path, encoding='utf-8', xml_declaration=True)
            with path.open('a', encoding='utf-8') as stream:
                stream.write('\n')

        # На узком экране подписи двух графиков лучше читаются друг под другом.
        fig, axes = plt.subplots(2, 1, figsize=(4.6, 6.8), layout='constrained')
        x = np.linspace(0, 4, 121)
        axes[0].plot(x, 2*x+5, color=BLUE)
        axes[0].scatter([0, 1, 3], [5, 7, 11], color=BLUE)
        axes[0].set(title='f(x) = 2x + 5', xlabel='Расстояние, км',
                    ylabel='Стоимость, руб.', xticks=[0, 1, 2, 3, 4], yticks=[5, 7, 9, 11, 13])
        x = np.linspace(0, 6, 181)
        axes[1].plot(x, (x-3)**2, color=BLUE)
        axes[1].scatter([3], [0], color=BLUE)
        axes[1].set(title='g(x) = (x − 3)²', xlabel='x', ylabel='g(x)',
                    xticks=[0, 1, 2, 3, 4, 5, 6], yticks=[0, 3, 6, 9])
        save(fig, 'functions', 'Линейная функция и квадрат со сдвигом',
             'Верхний график: стоимость 2x+5, точки (0,5), (1,7), (3,11). '
             'Нижний: (x−3)², минимум в точке (3,0).')

        fig, axes = plt.subplots(2, 1, figsize=(4.6, 6.8), layout='constrained')
        x = np.linspace(0, 2, 101)
        axes[0].plot(x, x+1, color=BLUE)
        axes[0].scatter([1], [2], s=65, facecolors='white', edgecolors=BLUE, zorder=3)
        axes[0].set(title='Предел 2 при x → 1', xlabel='x', ylabel='f(x)',
                    xticks=[0, 1, 2], yticks=[1, 2, 3])
        axes[1].plot([-1, 0], [-1, -1], color=BLUE)
        axes[1].plot([0, 1], [1, 1], color=BLUE)
        axes[1].scatter([0], [-1], s=65, facecolors='white', edgecolors=BLUE, zorder=3)
        axes[1].scatter([0], [1], s=65, color=BLUE, zorder=3)
        axes[1].set(title='Слева −1, справа 1', xlabel='x', ylabel='f(x)',
                    xticks=[-1, 0, 1], yticks=[-1, 0, 1], ylim=(-1.5, 1.5))
        save(fig, 'limits', 'Устранимый разрыв и скачок',
             'Сверху: (x²−1)/(x−1)=x+1 при x≠1, выколотая точка (1,2). '
             'Снизу: −1 при x<0 и 1 при x≥0; (0,−1) выколота, (0,1) включена.')

        fig, ax = plt.subplots(figsize=(4.6, 3.8), layout='constrained')
        x = np.linspace(.5, 3.5, 151)
        ax.plot(x, x*x, color=BLUE, label='f(x) = x²')
        ax.plot(x, 4+4*(x-2), '--', color=ORANGE, label='y = 4 + 4(x − 2)')
        ax.scatter([2], [4], color=ORANGE, zorder=3)
        ax.annotate('(2, 4)', (2, 4), xytext=(6, -22), textcoords='offset points')
        ax.set(xlabel='x', ylabel='Значение', xticks=[1, 2, 3], yticks=[0, 4, 8, 12])
        ax.legend(fontsize=11)
        save(fig, 'tangent', 'Квадрат и касательная',
             'Касательная к x² при x=2: y=4+4(x−2). Обе кривые проходят через (2,4).')

        fig, ax = plt.subplots(figsize=(4.6, 3.8), layout='constrained')
        x = np.linspace(-4, 4, 401)
        density = lambda z: np.exp(-z*z/2)/np.sqrt(2*np.pi)
        ax.plot(x, density(x), color=BLUE)
        shaded = np.linspace(-2, 2, 201)  # Включаем точные концы интервала заштрихованной области.
        ax.fill_between(shaded, 0, density(shaded), color=BLUE, alpha=.22)
        ax.set(title='Между −2 и 2: около 95%', xlabel='Стандартная координата z',
               ylabel='Плотность', xticks=[-4, -2, 0, 2, 4], ylim=(0, .44))
        save(fig, 'normal', 'Стандартная нормальная плотность',
             'Центр 0, стандартное отклонение 1. Площадь между −2 и 2 приблизительно 0.9545, '
             'а не высота плотности в точке.')

        fig, ax = plt.subplots(figsize=(4.6, 3.8), layout='constrained')
        x = np.linspace(-.2, 4.5, 151)
        ax.plot(x, (x-3)**2, color=BLUE)
        points = [0.]
        for _ in range(3):
            points.append(points[-1] - .25*2*(points[-1]-3))
        ax.scatter(points, [(v-3)**2 for v in points], color=ORANGE, zorder=3)
        for t, v in enumerate(points):
            ax.annotate(str(t), (v, (v-3)**2), xytext=(4, 6), textcoords='offset points')
        ax.set(title='Спуск при η = 0.25', xlabel='Параметр x', ylabel='f(x) = (x − 3)²',
               xticks=[0, 1, 2, 3, 4], yticks=[0, 3, 6, 9])
        save(fig, 'descent', 'Четыре точки градиентного спуска',
             'Цифры — номера шагов: x₀=0, x₁=1.5, x₂=2.25, x₃=2.625. '
             'Значения функции: 9, 2.25, 0.5625, 0.140625.')

        fig, ax = plt.subplots(figsize=(4.6, 3), layout='constrained')
        vertices = {'А': (0, 0), 'Б': (1, 1), 'В': (2, 0), 'Г': (3, 1)}
        for a, b in [('А', 'Б'), ('Б', 'В'), ('А', 'В')]:
            xy = np.array([vertices[a], vertices[b]])
            ax.plot(xy[:, 0], xy[:, 1], color=GRAY, zorder=1)
        for name, (x, y) in vertices.items():
            ax.scatter([x], [y], s=100, color=BLUE, zorder=2)
            ax.annotate(name, (x, y), xytext=(0, 12), ha='center', textcoords='offset points')
        ax.set(xlim=(-.3, 3.3), ylim=(-.3, 1.6), aspect='equal')
        ax.axis('off')
        save(fig, 'graph', 'Три ребра и четыре вершины',
             'Рёбра А—Б, Б—В и А—В образуют треугольник; Г изолирована. '
             'Координаты выбраны для рисунка и не задают веса рёбер.')

        fig, ax = plt.subplots(figsize=(4.6, 4), layout='constrained')
        u, y = np.array([1., 2.]), np.array([2., 1.])
        projection = u * (u@y)/(u@u)
        ax.plot([0, 1.25], [0, 2.5], color=GRAY, label='Прямая au')
        for point, color in [(y, BLUE), (projection, ORANGE)]:
            ax.annotate('', xy=point, xytext=(0, 0),
                        arrowprops={'arrowstyle': '->', 'color': color, 'lw': 2})
        ax.plot([projection[0], y[0]], [projection[1], y[1]], '--', color=GREEN)
        ax.annotate('y = (2, 1)', y, xytext=(3, -17), textcoords='offset points', fontsize=12)
        ax.annotate('(0.8, 1.6)', projection, xytext=(8, 4), textcoords='offset points', fontsize=12)
        # Значок прямого угла строим при одинаковом масштабе координат.
        along = u/np.linalg.norm(u)*.13
        across = (y-projection)/np.linalg.norm(y-projection)*.13
        corner = np.array([projection+along, projection+along+across, projection+across])
        ax.plot(corner[:, 0], corner[:, 1], color=GREEN)
        ax.set(xlabel='Первая координата', ylabel='Вторая координата',
               xlim=(-.1, 2.9), ylim=(-.1, 2.9), aspect='equal', xticks=[0, 1, 2], yticks=[0, 1, 2])
        ax.legend(fontsize=11, loc='upper right')
        save(fig, 'projection', 'Проекция на направление (1,2)',
             'Синяя стрелка y=(2,1), оранжевая проекция (0.8,1.6). '
             'Зелёный пунктир — остаток (1.2,−0.6), перпендикулярный прямой au при u=(1,2). '
             'Масштабы обеих координат одинаковы.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'handbooks/data/figures')
    generate(parser.parse_args().output)
