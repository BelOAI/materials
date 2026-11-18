В одной стране и категории могут выступать несколько спортсменов с похожей статистикой. Поэтому сначала оценим кандидатов для каждой строки, а затем согласуем прогнозы для всех строк группы.

Для каждой строки рассматриваем спортсменов той же страны и категории из обучающей таблицы. Сравниваем статистику с их предыдущими сезонами, придавая более свежим результатам больший вес. Чтобы сопоставить разные дисциплины, учитываем разницу между их средними показателями. В оценке сходства используем число гонок: при малом числе стартов расширяем диапазон различий, при которых две строки считаются близкими. Бустинг учится оценивать кандидатов на исторических сезонах, используя для каждого сезона признаки только из предшествующих ему лет.

Например, для строки итальянской спортсменки в спринте сначала оценим каждую итальянскую спортсменку из обучающей таблицы. Для каждого имени объединим оценку бустинга и сходство с историей. Затем назначим имена всем строкам итальянского женского спринта совместно. Второй бустинг оценивает совместимость строк из разных дисциплин. Если строка из преследования похожа на результат той же спортсменки, общая оценка такого назначения растёт. Алгоритм пробует несколько начальных назначений и выбирает вариант с наибольшей оценкой среди полученных.

Внутри дисциплины обычно используем каждое имя не более одного раза. Полностью совпадающие по входным полям строки обрабатываем как одну и возвращаем им одинаковый прогноз. Если на всех разных строк кандидатов не хватает, разрешаем повтор имени со штрафом. Когда в обучении нет спортсменов данной страны и категории, используем самое частое имя из обучающей таблицы. Такой отбор по стране напрямую не учитывает переходы спортсменов между странами.

### Проверка качества

На валидации 2024/25 модель обучалась на `train.csv` и получила Macro-F1 **0,458**. Для отдельной авторской проверки на сезоне 2025/26 модель обучалась на объединённых `train.csv` и `validation.csv`. В обоих случаях сначала получали предсказания и только затем сравнивали их с правильными именами.

*Таблица 1 — Результаты авторской проверки на сезоне 2025/26*

| Часть | Macro-F1 | Балл |
| :--- | ---: | ---: |
| Публичная | 0,353 | 47,0847 |
| Скрытая | 0,380 | 50,7116 |

С учётом весов двух частей получается $0{,}2\cdot47{,}0847+0{,}8\cdot50{,}7116\approx49{,}9862$, то есть **49,99 балла** после округления до сотых. На каждой из двух частей вызов `predict` занял около 2,5 секунды. Замер охватывал работу функции, включая обучение внутри неё. Запуск Python и импорт библиотек в замер не входили.

Листинг использует SciPy для задачи о назначениях и threadpoolctl для ограничения числа потоков. Обе библиотеки устанавливаются вместе со scikit-learn.

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
