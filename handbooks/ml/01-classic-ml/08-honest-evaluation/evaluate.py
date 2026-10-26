"""Повторная проверка настроек и однократная итоговая оценка."""

from pathlib import Path

import pandas as pd
from sklearn.metrics import mean_absolute_error
from sklearn.model_selection import KFold
from sklearn.tree import DecisionTreeRegressor


HERE = Path(__file__).resolve().parent
FEATURES = ["height_cm", "colors", "plastic_cm3"]
train = pd.read_csv(HERE / "../07-features-regularization/data/train.csv")
final = pd.read_csv(HERE / "data/final.csv")
answers = pd.read_csv(HERE / "data/final_answers.csv")
assert len(train) == 300 and len(final) == len(answers) == 100
assert set(train.order_id).isdisjoint(final.order_id)

settings = {
    "глубина 2": {"max_depth": 2},
    "глубина 4": {"max_depth": 4},
    "от 5 в листе": {"min_samples_leaf": 5},
    "без ограничения": {},
}
folds = KFold(n_splits=3, shuffle=True, random_state=42)
scores = {}
for name, params in settings.items():
    errors = []
    for fit_idx, valid_idx in folds.split(train):
        fit_rows, valid_rows = train.iloc[fit_idx], train.iloc[valid_idx]
        model = DecisionTreeRegressor(random_state=0, **params)
        model.fit(fit_rows[FEATURES], fit_rows.minutes)
        errors.append(mean_absolute_error(
            valid_rows.minutes, model.predict(valid_rows[FEATURES])
        ))
    scores[name] = errors
    print(name, "фолды:", *(f"{error:.2f}" for error in errors),
          "средняя:", f"{sum(errors) / len(errors):.2f}")

winner = min(settings, key=lambda name: sum(scores[name]) / len(scores[name]))
print("Выбрана настройка:", winner)
model = DecisionTreeRegressor(random_state=0, **settings[winner])
model.fit(train[FEATURES], train.minutes)
checked = final.merge(answers, on="order_id", validate="one_to_one",
                      suffixes=("_hidden", ""))
assert len(checked) == 100
assert checked.minutes_hidden.eq("?").all()
print("Итоговая MAE:", f"{mean_absolute_error(checked.minutes, model.predict(checked[FEATURES])):.2f}")
