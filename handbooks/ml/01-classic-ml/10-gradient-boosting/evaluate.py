"""Воспроизводимое сравнение моделей для занятия 1.10."""

from pathlib import Path

import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error
from sklearn.model_selection import KFold, cross_val_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


HERE = Path(__file__).resolve().parent
FEATURES = ["height_cm", "colors", "plastic_cm3"]
train = pd.read_csv(HERE / "../07-features-regularization/data/train.csv")
X, y = train[FEATURES], train["minutes"]

models = {
    "Линейная модель (Ridge)": make_pipeline(StandardScaler(), Ridge(alpha=1)),
    "Случайный лес": RandomForestRegressor(
        n_estimators=100, max_features=2, random_state=42
    ),
    "Бустинг, 20 деревьев": GradientBoostingRegressor(
        n_estimators=20, learning_rate=0.1, max_depth=2,
        min_samples_leaf=5, random_state=42
    ),
    "Бустинг, 100 деревьев": GradientBoostingRegressor(
        n_estimators=100, learning_rate=0.1, max_depth=2,
        min_samples_leaf=5, random_state=42
    ),
}

folds = KFold(n_splits=3, shuffle=True, random_state=42)
scores = {}
for name, model in models.items():
    errors = -cross_val_score(
        model, X, y, cv=folds, scoring="neg_mean_absolute_error"
    )
    scores[name] = errors.mean()
    print(name, [round(value, 2) for value in errors], round(scores[name], 2))

winner = min(scores, key=scores.get)
model = models[winner].fit(X, y)
final = pd.read_csv(HERE / "data/final.csv")
assert final["minutes"].eq("?").all()
predictions = model.predict(final[FEATURES])

# Открываем ответы только после выбора модели и фиксации прогнозов.
answers = pd.read_csv(HERE / "data/final_answers.csv")
checked = final[["order_id"]].merge(answers, on="order_id", validate="one_to_one")
assert len(checked) == len(final) == 100
print("Выбрана модель:", winner)
print("Итоговая MAE:", round(mean_absolute_error(checked["minutes"], predictions), 2))
