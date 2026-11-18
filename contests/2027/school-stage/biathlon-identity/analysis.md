В одной стране и категории могут выступать несколько спортсменов с похожей статистикой. Если выбирать имя для каждой строки отдельно, алгоритм может назначить его двум участникам одной дисциплины. Поэтому сначала оценим кандидатов для каждой строки, затем согласуем предсказания по дисциплинам.

Для каждого кандидата сравним новую строку с его статистикой прошлых лет. Более свежие сезоны весят сильнее. Средние показатели корректируем на различия между дисциплинами, а число гонок используем как оценку надёжности: профиль спортсмена с малым числом стартов сильнее сглаживаем и слабее штрафуем за расхождение. Градиентный бустинг учится ранжировать кандидатов на последовательных срезах: для каждого исторического сезона признаки строятся только по предыдущим сезонам.

Второй бустинг оценивает, насколько строки из разных дисциплин похожи на результаты одного спортсмена. Его оценка помогает согласовать решения по строкам целевого сезона. Для каждой страны и категории отдельно решаем задачу назначений по дисциплинам, ограничивая повторное использование имени внутри одной дисциплины. Несколько стартовых назначений и итеративное согласование междисциплинарных пар помогают выбрать вариант с наибольшей общей оценкой.

### Проверка качества

Ранжировщик обучается на последовательных сезонных срезах: кандидаты для каждого сезона сравниваются только с историей до этого сезона. После выбора модели авторский бенчмарк сначала получает предсказания, а затем сравнивает их с правильными именами.

*Таблица 1 — Macro-F1 и баллы по авторскому чекеру*

| Решение | Валидация 2024/25 | Публичная часть | Скрытая часть | Баллы за тест |
| --- | ---: | ---: | ---: | ---: |
| Модель из листинга | 0,458 | 0,353 | 0,380 | 49,99 |

Тестовый балл — взвешенное среднее: $0{,}2\cdot47{,}0847+0{,}8\cdot50{,}7116=49{,}9862$, то есть **49,99 балла** после округления до сотых. Порог в 100 баллов требует Macro-F1 не ниже 0,75 в обеих частях; это решение его не достигает. Время одного вызова `predict` в авторском бенчмарке составило около 2,5 секунды на публичной и скрытой частях. Используются SciPy для задачи о назначениях и threadpoolctl для ограничения числа потоков; обе библиотеки устанавливаются вместе со scikit-learn.

```python
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from threadpoolctl import threadpool_limits
from scipy.optimize import linear_sum_assignment

categories = ['country', 'gender']
numeric = ['misses_per_race', 'shooting_time_s', 'races']
disciplines = ['SP', 'IN', 'PU', 'MS']


def candidate_features(train, test, with_prior=False):
    train = train.assign(d=train.discipline.map(disciplines.index))
    test = test.assign(d=test.discipline.map(disciplines.index)).reset_index(drop=True)
    prior_scores = []
    if with_prior:
        means = train.groupby(['gender', 'd'])[numeric].mean()
    scale = np.array([1.8, 4.0, 1.0])
    offset = train.groupby('d')[numeric].mean().reindex(range(4)).to_numpy()
    historical = {key: history for key, history in train.groupby(categories)}
    all_x, all_rows, all_names = [], [], []
    for key, rows in test.groupby(categories):
        if key not in historical:
            continue
        q = rows[numeric].to_numpy()
        qdisc = rows.d.to_numpy(dtype=int)
        qyear = rows.season_end.to_numpy()
        qadj = q - offset[qdisc]
        for name, history in historical[key].groupby('label'):
            h = history[numeric].to_numpy()
            hdisc = history.d.to_numpy(dtype=int)
            hyear = history.season_end.to_numpy()
            age = qyear[:, None] - hyear
            recent = np.exp(-0.7 * (age - 1))
            same = qdisc[:, None] == hdisc
            delta = np.abs(q[:, None] - h[None, :]) / scale
            h_adj = h - offset[hdisc]
            adjusted_delta = np.abs(qadj[:, None] - h_adj[None, :]) / scale
            feats = [q, qdisc[:, None], np.broadcast_to([len(history), len(rows)], (len(q), 2))]
            for mask, diff in [(same, delta), (np.ones_like(same), adjusted_delta)]:
                w = recent * mask
                wtotal = w.sum(axis=1)
                mean = w @ (h if diff is delta else h_adj) / np.maximum(wtotal[:, None], 1e-10)
                squared = np.square(diff[:, :, :2]).sum(axis=2)
                dist = np.sqrt(squared)
                latest = np.where(mask, age, 99).min(axis=1)
                closest = np.where(mask, dist + 0.5 * (age - 1), np.inf).min(axis=1)
                newest = w * (age == latest[:, None])
                nearest = np.where(newest > 0, dist, np.inf).min(axis=1)
                feats += [np.column_stack([mask.sum(axis=1), wtotal, latest, closest, nearest]),
                          mean, np.abs((q if diff is delta else qadj)-mean),
                          np.sum(w[:, :, None] * diff, axis=1)/np.maximum(wtotal[:, None], 1e-10)]
            for disc in range(4):
                mask = (hdisc == disc)[None, :]
                feats += [np.column_stack([(recent * mask).sum(axis=1),
                            np.where(mask, age, 99).min(axis=1),
                            (recent * mask) @ h[:, 2]])]
            if with_prior:
                discipline_means = means.loc[key[1]].reindex(range(4)).to_numpy()
                shift = discipline_means[qdisc, None] - discipline_means[hdisc]
                difference = q[:, None] - h - shift
                width_squared = 0.5 + 0.75 / q[:, None, 2] + 0.75 / h[:, 2]
                squared = np.square(difference[:, :, :2] / [1.5, 2.8]).sum(axis=2)
                mass = np.exp(-0.5 * squared / width_squared) / width_squared
                mass *= np.exp(-0.2 * np.abs(difference[:, :, 2]))
                weights = (0.75 + 0.25 * same) * recent
                density = (weights * mass).sum(axis=1) / weights.sum(axis=1)
                prior_scores.extend(np.log(density + 1e-10)
                                    + np.log(weights.sum(axis=1) + 0.01))
            all_x.append(np.column_stack(feats))
            all_rows.extend(rows.index)
            all_names.extend([name] * len(rows))
    if not all_x:
        return np.empty((0, 0)), np.array([], dtype=int), np.array([]), np.array([])
    x = np.concatenate(all_x)
    x[~np.isfinite(x)] = np.nan
    return x, np.array(all_rows), np.array(all_names), np.array(prior_scores)


def fit_ranker(train):
    data = []
    for year in sorted(train.season_end.unique())[2:]:
        prior = train[train.season_end < year]
        valid = train[train.season_end == year]
        x, indices, labels, _ = candidate_features(prior, valid.drop(columns='label'))
        data.append((x, (valid.label.to_numpy()[indices] == labels)))
    x, y = map(np.concatenate, zip(*data))
    model = HistGradientBoostingClassifier(
        max_iter=130, max_leaf_nodes=20, l2_regularization=4, random_state=7,
    )
    return model.fit(x, y)


def compatibility(rows, averages):
    disc = rows.discipline.map(disciplines.index).to_numpy(dtype=int)
    values = rows[numeric].to_numpy(dtype=float)
    centered = values - averages[disc]
    i, j = np.where(disc[:, None] < disc[None, :])
    nf = np.abs(values[i] - values[j])
    cf = np.abs(centered[i] - centered[j])
    features = np.column_stack([disc[i], disc[j], values[i], values[j], nf, cf])
    return i, j, features


def fit_pairs(train):
    averages = train.groupby('discipline')[numeric].mean().reindex(disciplines).to_numpy()
    data = []
    for _, rows in train.groupby(['season_end', *categories]):
        i, j, features = compatibility(rows, averages)
        labels = rows.label.to_numpy()
        data.append((features, labels[i] == labels[j]))
    x, y = map(np.concatenate, zip(*data))
    reg = HistGradientBoostingClassifier(
        max_iter=100, max_leaf_nodes=12, l2_regularization=5, random_state=0,
    )
    return averages, reg.fit(x, y)


def assign_names(test, idx, names, scores, fallback, averages, pair_model):
    predictions = np.full(len(test), fallback, dtype=object)
    name_codes, identities = pd.factorize(names, sort=True)
    score_table = np.full((len(test), len(identities)), -np.inf)
    score_table[idx, name_codes] = scores

    def assignment(values):
        rows, columns = linear_sum_assignment(values, maximize=True)
        return columns[np.argsort(rows)]

    test = test.reset_index(drop=True)
    for rows in test.groupby(categories).indices.values():
        # Use the same search order for any permutation of the input.
        group = test.iloc[rows].sort_values(['discipline', *numeric])
        rows = group.index.to_numpy()
        candidates = np.flatnonzero(np.isfinite(score_table[rows]).any(axis=0))
        if not len(candidates):
            continue
        base = score_table[np.ix_(rows, candidates)]
        partitions = [
            np.flatnonzero(group.discipline.to_numpy() == discipline)
            for discipline in disciplines
        ]
        if max(map(len, partitions)) > len(candidates):
            # Permit repeats with a large penalty when the pool is too small.
            repeats = np.tile(base - 20, (1, len(rows) - 1))
            base = np.column_stack([base, repeats])

        left, right, features = compatibility(group, averages)
        affinity = np.zeros((len(rows), len(rows)))
        if len(left):
            log_odds = pair_model.decision_function(features)
            affinity[left, right] = affinity[right, left] = (
                0.15 * np.clip(log_odds + 1, -4, 3)
            )

        best_score = -np.inf
        random = np.random.default_rng(42)
        for restart in range(6):
            seed = base if restart == 0 else base + random.normal(0, 0.5, base.shape)
            chosen = np.zeros(len(rows), dtype=int)
            for part in partitions:
                chosen[part] = assignment(seed[part])
            for _ in range(5):
                previous = chosen.copy()
                for part in partitions:
                    bonus = np.zeros_like(base[part])
                    for row, name in enumerate(chosen):
                        bonus[:, name] += affinity[part, row]
                    chosen[part] = assignment(base[part] + bonus)
                if np.array_equal(chosen, previous):
                    break
            score = base[np.arange(len(rows)), chosen].sum()
            score += 0.5 * (affinity * (chosen[:, None] == chosen)).sum()
            if score > best_score:
                best_score = score
                best = chosen.copy()
        predictions[rows] = identities[candidates[best % len(candidates)]]
    return predictions


def predict(train, test):
    if test.empty:
        return []
    columns = ['season_end', *categories, 'discipline', *numeric]
    keys = pd.MultiIndex.from_frame(test[columns])
    first = ~keys.duplicated()
    inverse = keys[first].get_indexer(keys)
    test = test.iloc[first]
    fallback = train.label.mode()[0]
    with threadpool_limits(limits=2):
        features, rows, names, profile_scores = candidate_features(train, test, with_prior=True)
        if not len(rows):
            return [fallback] * len(keys)
        ranker = fit_ranker(train)
        averages, pair_model = fit_pairs(train)
        scores = 0.5 * (ranker.decision_function(features) + profile_scores)
        result = assign_names(test, rows, names, scores, fallback, averages, pair_model)
    return result[inverse].tolist()
```
