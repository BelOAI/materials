# Эмбеддинги и представление текста

От one-hot и мешка слов к эмбеддингам: классифицируем отзывы мешком слов, ищем соседей по косинусному сходству, считаем совместную встречаемость, обучаем word2vec из библиотеки gensim и смотрим на соседей, аналогии и антонимы в векторах GloVe.

[Текст](content.md) · [Ноутбук](notebook.ipynb) · [Код рисунков](figures.py) · [One-hot](media/onehot.svg) · [Расстояние и угол](media/compare.svg) · [Мешок слов](media/bow.svg) · [Таблица мешков](media/bow-matrix.svg) · [Таблица эмбеддингов](media/lookup.svg) · [Окно контекста](media/window.svg) · [Таблица соседей](media/cooc.svg) · [Схема word2vec](media/skipgram.svg) · [Карта слов](media/wordmap.svg)

Нужны векторы, скалярное произведение, логистическая регрессия из [занятия 1.6](../../01-classic-ml/06-logistic-regression/README.md). Для word2vec нужна библиотека gensim: она добавлена в `requirements.txt` учебника, в Colab её ставят через `%pip install gensim`. Отзывы и датасет из десяти предложений придуманы для занятия.

## Данные

`data/glove-twitter.npz` — 10 000 самых частых английских и 2500 самых частых русских слов из векторов GloVe Twitter (100 измерений, float16). Исходник — `glove-twitter-100` из [gensim-data](https://github.com/RaRe-Technologies/gensim-data), выпущенный Stanford NLP под [PDDL 1.0](https://opendatacommons.org/licenses/pddl/1-0/). Выборку собирает `python3 data/generate.py путь/к/glove-twitter-100.gz`.

Рисунки — SVG с прозрачным фоном и цветами для светлой, тёмной и печатной темы; их собирает `python3 figures.py` (нужны numpy, scikit-learn и gensim; карту слов строит t-SNE из scikit-learn). Вероятности на `skipgram.svg` взяты из той же модели gensim, что и в тексте (`seed=0`, `workers=1`, результат повторяется). Выводы листингов в тексте сверяются с реальным запуском. Ноутбук синхронизируется с текстом: `python3 utils/scripts/handbook_notebooks.py --write`.

## Источники

- J. R. Firth. A Synopsis of Linguistic Theory 1930–1955. 1957 — дистрибутивная гипотеза («You shall know a word by the company it keeps»); в тексте изложена как правило «похожие соседи — похожий смысл».
- T. Mikolov et al. Efficient Estimation of Word Representations in Vector Space. 2013, [arXiv:1301.3781](https://arxiv.org/abs/1301.3781) — word2vec; skip-gram с полным softmax упрощён для учебного датасета.
- T. Mikolov, W. Yih, G. Zweig. Linguistic Regularities in Continuous Space Word Representations. NAACL 2013 — аналогии через разности векторов.
- J. Pennington, R. Socher, C. Manning. GloVe: Global Vectors for Word Representation. EMNLP 2014, [nlp.stanford.edu/projects/glove](https://nlp.stanford.edu/projects/glove/) — модель и векторы GloVe.

Числа в тексте проверены запуском листингов (PyTorch 2.14.1 CPU, scikit-learn 1.9.1, numpy 2.5.4).
