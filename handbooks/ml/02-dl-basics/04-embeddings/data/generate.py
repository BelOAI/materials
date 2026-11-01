"""Собрать data/glove-twitter.npz из GloVe Twitter-100.

Исходник: glove-twitter-100.gz из gensim-data (Stanford NLP, PDDL 1.0).
Запуск: python3 generate.py путь/к/glove-twitter-100.gz
Файл упорядочен по частоте; берём 10 000 самых частых английских
и 2500 самых частых русских слов, векторы сохраняем во float16.
"""
import gzip
import re
import sys
from pathlib import Path

import numpy as np

N_LATIN, N_CYRILLIC = 10_000, 2_500
LATIN, CYRILLIC = re.compile(r"[a-z]+"), re.compile(r"[а-яё]+")

words, vectors = [], []
latin = cyrillic = 0
with gzip.open(sys.argv[1], "rt", encoding="utf-8") as source:
    next(source)  # заголовок: число слов и размерность
    for line in source:
        word, *values = line.rstrip().split(" ")
        if LATIN.fullmatch(word) and latin < N_LATIN:
            latin += 1
        elif CYRILLIC.fullmatch(word) and cyrillic < N_CYRILLIC:
            cyrillic += 1
        else:
            if latin == N_LATIN and cyrillic == N_CYRILLIC:
                break
            continue
        words.append(word)
        vectors.append(np.array(values, dtype=np.float32))

np.savez_compressed(Path(__file__).with_name("glove-twitter.npz"),
                    words=np.array(words), vectors=np.stack(vectors).astype(np.float16))
print(len(words), "слов")
