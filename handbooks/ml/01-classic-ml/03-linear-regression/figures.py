"""Построить рисунки занятия: python3 figures.py (SVG появятся в media/).

Все данные учебные и синтетические; генератор данных совпадает с листингом в content.md.
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from sklearn.linear_model import Lasso, LinearRegression, Ridge
from sklearn.metrics import mean_squared_error
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import PolynomialFeatures, StandardScaler

MEDIA = Path(__file__).resolve().parent / "media"
BLUE, ORANGE, GREEN, RED, GRAY = "#2563eb", "#b45309", "#15803d", "#b91c1c", "#64748b"
LIGHT = "#cbd5e1"

plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 10.5, "axes.titlesize": 11.5,
    "axes.spines.top": False, "axes.spines.right": False,
    "svg.fonttype": "path", "svg.hashsalt": "beloai-linear-regression",
    "axes.grid": True, "grid.color": "#e2e8f0", "grid.linewidth": 0.8,
    "legend.frameon": False, "mathtext.fontset": "dejavusans",
})


def save(fig, name):
    path = MEDIA / f"{name}.svg"
    fig.savefig(path, metadata={"Date": None, "Creator": "Авторы BelOAI"})
    plt.close(fig)
    # matplotlib оставляет пробелы в конце строк; убираем их для git diff --check.
    lines = path.read_text(encoding="utf-8").splitlines()
    path.write_text("\n".join(line.rstrip() for line in lines) + "\n", encoding="utf-8")


def rmse(a, b):
    return mean_squared_error(a, b) ** 0.5


# --- данные урока ---------------------------------------------------------
x4 = np.array([1.0, 2.0, 3.0, 4.0])
y4 = np.array([3.0, 5.0, 4.0, 8.0])
W, B = 1.4, 1.5  # метод наименьших квадратов для четырёх точек


def make_dataset():
    rng = np.random.default_rng(7)
    X = rng.normal(size=(90, 12))
    X[:, 3] = X[:, 0] + 0.2 * rng.normal(size=90)
    true_w = np.array([3, -2, 1.5, 0, 0, 0, 0, 0, 0, 0, 0, 0.0])
    y = 5 + X @ true_w + 2.0 * rng.normal(size=90)
    return X, y, true_w


def mse4(w, b):
    return float(np.mean((w * x4 + b - y4) ** 2))


# --- 1. прямая и остатки --------------------------------------------------
def fig_fit():
    fig, axes = plt.subplots(1, 2, figsize=(7.6, 3.3), sharey=True, layout="constrained")
    t = np.linspace(0.3, 4.7, 50)
    ax = axes[0]
    ax.plot(t, W * t + B, color=BLUE, lw=2, label=r"$\hat{y}=1{,}4\,x+1{,}5$")
    ax.axhline(y4.mean(), color=GRAY, ls="--", lw=1.4, label="среднее $\\bar{y}=5$")
    for xi, yi in zip(x4, y4):
        ax.plot([xi, xi], [yi, W * xi + B], color=ORANGE, lw=2)
    ax.scatter(x4, y4, color="black", zorder=3)
    for xi, yi, e in zip(x4, y4, y4 - (W * x4 + B)):
        ax.annotate(f"{e:+.1f}".replace(".", ",").replace("-", "−"), (xi, (yi + W * xi + B) / 2),
                    xytext=(7, 0), textcoords="offset points", color=ORANGE, va="center")
    ax.set(title="Остатки $e_i=y_i-\\hat{y}_i$", xlabel="часы подготовки $x$",
           ylabel="балл $y$", xlim=(0.3, 4.7), ylim=(0, 9.5))
    ax.legend(loc="upper left")
    ax = axes[1]
    for (w, b), c in zip([(W, B), (0.5, 3.5), (2.5, -1.5)], [BLUE, GREEN, RED]):
        ax.plot(t, w * t + b, color=c, lw=2,
                label=f"w={w:g}, b={b:g}: MSE={mse4(w, b):.2f}".replace(".", ",").replace("-", "−"))
    ax.scatter(x4, y4, color="black", zorder=3)
    ax.set(title="Три прямые: у лучшей MSE меньше", xlabel="часы подготовки $x$",
           xlim=(0.3, 4.7))
    ax.legend(loc="upper left", fontsize=9.5)
    save(fig, "fit-residuals")


# --- 2. поверхность потерь и градиентный спуск ----------------------------
def fig_surface():
    fig, axes = plt.subplots(1, 2, figsize=(7.6, 3.4), layout="constrained")
    ws = np.linspace(-0.6, 3.0, 200)
    bs = np.linspace(-2.5, 6.5, 200)
    Wg, Bg = np.meshgrid(ws, bs)
    Z = ((Wg[..., None] * x4 + Bg[..., None] - y4) ** 2).mean(axis=-1)
    ax = axes[0]
    ax.contour(Wg, Bg, Z, levels=[1.5, 3, 6, 12, 25, 50], colors="#94a3b8", linewidths=1.0)
    path, losses, w, b = [(0.0, 0.0)], [mse4(0, 0)], 0.0, 0.0
    for _ in range(300):
        e = w * x4 + b - y4
        w, b = w - 0.05 * 2 * np.mean(e * x4), b - 0.05 * 2 * np.mean(e)
        path.append((w, b))
        losses.append(mse4(w, b))
    path = np.array(path)
    ax.plot(path[:8, 0], path[:8, 1], "-o", color=ORANGE, ms=4, lw=1.4, label="первые 7 шагов")
    ax.plot(path[7:, 0], path[7:, 1], "-", color=ORANGE, lw=1, alpha=.6)
    ax.scatter([W], [B], marker="*", s=170, color=BLUE, zorder=4, label="МНК: $w=1{,}4,\\ b=1{,}5$")
    ax.annotate("старт (0; 0)", (0, 0), xytext=(0.4, -1.6), color=ORANGE,
                arrowprops=dict(arrowstyle="->", color=ORANGE))
    ax.set(title="Линии уровня MSE в плоскости $(w,b)$", xlabel="наклон $w$", ylabel="сдвиг $b$")
    ax.legend(loc="upper right", fontsize=9)
    ax = axes[1]
    ax.plot(np.arange(len(losses)), losses, color=ORANGE, lw=2)
    ax.axhline(mse4(W, B), color=BLUE, ls="--", lw=1.4, label="минимум 1,05")
    ax.set(title="MSE по шагам градиентного спуска", xlabel="номер шага", ylabel="MSE",
           yscale="log")
    ax.legend()
    save(fig, "loss-surface")
    return path, losses


# --- 3. выбросы и коллинеарность ------------------------------------------
def fig_pitfalls():
    fig, axes = plt.subplots(1, 2, figsize=(7.6, 3.4), layout="constrained")
    ax = axes[0]
    rng = np.random.default_rng(3)
    x = np.linspace(1, 8, 8)
    y = 1 + 0.8 * x + rng.normal(0, 0.4, 8)
    xo, yo = np.append(x, 8.5), np.append(y, 0.5)
    t = np.linspace(0.5, 9, 10)
    f1, f2 = np.polyfit(x, y, 1), np.polyfit(xo, yo, 1)
    ax.plot(t, np.polyval(f1, t), color=BLUE, lw=2, label=f"без выброса: w={f1[0]:.2f}".replace(".", ","))
    ax.plot(t, np.polyval(f2, t), color=RED, lw=2, label=f"с выбросом: w={f2[0]:.2f}".replace(".", ","))
    ax.scatter(x, y, color="black", zorder=3)
    ax.scatter([8.5], [0.5], color=RED, marker="s", s=60, zorder=3)
    ax.set(title="Один выброс тянет прямую", xlabel="$x$", ylabel="$y$", xlim=(0.5, 9.2))
    ax.legend(loc="upper left", fontsize=9.5)
    ax = axes[1]
    rng = np.random.default_rng(11)
    ols, rid = [], []
    for _ in range(150):
        x1 = rng.normal(size=20)
        x2 = x1 + 0.1 * rng.normal(size=20)
        yy = x1 + x2 + rng.normal(0, 1, 20)
        Xm = np.c_[x1, x2]
        ols.append(LinearRegression().fit(Xm, yy).coef_)
        rid.append(Ridge(alpha=5).fit(Xm, yy).coef_)
    ols, rid = np.array(ols), np.array(rid)
    ax.scatter(*ols.T, s=12, color=RED, alpha=.55, label="МНК")
    ax.scatter(*rid.T, s=22, color=BLUE, alpha=.7, label="Ridge")
    ax.scatter([1], [1], marker="*", s=190, color="black", zorder=4, label="истина (1; 1)")
    ax.set(title="Похожие признаки: веса «гуляют»", xlabel="вес $w_1$", ylabel="вес $w_2$")
    ax.legend(fontsize=9.5)
    save(fig, "pitfalls")


# --- 4. переобучение полиномом --------------------------------------------
def fig_overfit():
    rng = np.random.default_rng(7)
    f = lambda x: np.sin(2 * np.pi * x)
    xtr = np.sort(rng.uniform(0, 1, 12))
    ytr = f(xtr) + rng.normal(0, 0.25, 12)
    xva = rng.uniform(0, 1, 60)
    yva = f(xva) + rng.normal(0, 0.25, 60)
    t = np.linspace(0, 1, 300)
    models = [
        ("Прямая (степень 1)", make_pipeline(PolynomialFeatures(1), LinearRegression())),
        ("Степень 9, без штрафа", make_pipeline(PolynomialFeatures(9), StandardScaler(), LinearRegression())),
        ("Степень 9 + Ridge", make_pipeline(PolynomialFeatures(9), StandardScaler(), Ridge(alpha=0.01))),
    ]
    fig, axes = plt.subplots(1, 3, figsize=(7.8, 3.0), sharey=True, layout="constrained")
    rows = []
    for ax, (title, model) in zip(axes, models):
        model.fit(xtr[:, None], ytr)
        tr = rmse(ytr, model.predict(xtr[:, None]))
        va = rmse(yva, model.predict(xva[:, None]))
        rows.append((title, tr, va))
        ax.plot(t, f(t), color=LIGHT, lw=2, label="истина")
        ax.plot(t, model.predict(t[:, None]), color=BLUE, lw=2, label="модель")
        ax.scatter(xtr, ytr, color="black", s=22, zorder=3, label="train")
        ax.set_title(title, fontsize=10)
        ax.set_xlabel(f"RMSE train {tr:.2f} / проверка {va:.2f}".replace(".", ","), fontsize=9.5)
        ax.set_ylim(-1.8, 1.8)
        ax.set_xticks([0, 0.5, 1], ["0", "0,5", "1"])
    axes[0].legend(loc="upper right", fontsize=8.5)
    save(fig, "overfit-poly")
    return rows


# --- 5. геометрия: круг и ромб ---------------------------------------------
def fig_geometry():
    A = np.array([[1.0, 0.7], [0.7, 1.0]])
    A = np.array([[2.0, 1.2], [1.2, 1.0]])
    w0 = np.array([2.2, 0.9])
    loss = lambda w: np.einsum("...i,ij,...j->...", w - w0, A, w - w0)
    grid = np.linspace(-1.4, 3.4, 400)
    G = np.stack(np.meshgrid(grid, grid), axis=-1)
    L = loss(G)
    ang = np.linspace(0, 2 * np.pi, 800)
    fig, axes = plt.subplots(1, 2, figsize=(7.6, 3.7), layout="constrained")
    t = 1.3
    for ax, kind in zip(axes, ("l2", "l1")):
        if kind == "l2":
            pts = np.c_[t * np.cos(ang), t * np.sin(ang)]
            inside = (G ** 2).sum(-1) <= t ** 2
            title = "Ridge: область $w_1^2+w_2^2\\leq t^2$"
        else:
            u = np.linspace(0, 1, 200)
            pts = np.concatenate([np.c_[t * u, t * (1 - u)], np.c_[t * (1 - u), -t * u],
                                  np.c_[-t * u, -t * (1 - u)], np.c_[-t * (1 - u), t * u]])
            inside = np.abs(G).sum(-1) <= t
            title = "Lasso: область $|w_1|+|w_2|\\leq t$"
        best = np.where(inside, L, np.inf)
        idx = np.unravel_index(np.argmin(best), best.shape)
        wstar = G[idx]
        ax.fill(*pts.T, color=BLUE, alpha=.14)
        ax.plot(*np.vstack([pts, pts[:1]]).T, color=BLUE, lw=2)
        ax.contour(G[..., 0], G[..., 1], L, levels=[0.25, 0.8, 1.7, 3, float(loss(wstar))],
                   colors=[LIGHT, LIGHT, LIGHT, LIGHT, ORANGE], linewidths=[1.1, 1.1, 1.1, 1.1, 2])
        ax.scatter(*w0, marker="*", s=170, color="black", zorder=4)
        ax.annotate("МНК", w0, xytext=(8, 6), textcoords="offset points")
        ax.scatter(*wstar, s=70, color=RED, zorder=5)
        w1s, w2s = wstar[0], abs(wstar[1]) if abs(wstar[1]) < 0.02 else wstar[1]
        ax.text(0.03, 0.97, f"● решение\n({w1s:.2f}; {w2s:.2f})".replace(".", ","),
                transform=ax.transAxes, color=RED, va="top", fontsize=9.5)
        ax.axhline(0, color=GRAY, lw=1)
        ax.axvline(0, color=GRAY, lw=1)
        ax.set(title=title, xlabel="$w_1$", ylabel="$w_2$", xlim=(-1.6, 3.3), ylim=(-1.6, 2.4), aspect="equal")
        ax.grid(False)
    save(fig, "geometry")


# --- 6. сжатие и мягкий порог ----------------------------------------------
def fig_shrink():
    fig, axes = plt.subplots(1, 2, figsize=(7.6, 3.3), layout="constrained")
    z = np.linspace(-3, 3, 400)
    s = 1.0
    ax = axes[0]
    ax.plot(z, z, color=GRAY, ls="--", lw=1.4, label="без штрафа")
    ax.plot(z, z / (1 + s), color=BLUE, lw=2, label="Ridge: $z/(1+t)$")
    ax.plot(z, np.sign(z) * np.maximum(np.abs(z) - s, 0), color=ORANGE, lw=2,
            label="Lasso: мягкий порог")
    ax.set(title="Вес после штрафа при $t=1$", xlabel="вес $z$ без штрафа", ylabel="вес с штрафом",
           xlim=(-3, 3), ylim=(-3, 3), aspect="equal")
    ax.legend(loc="upper left", fontsize=9.5)
    ax = axes[1]
    w = np.linspace(-1, 3, 400)
    z0 = 0.8
    ax.plot(w, 0.5 * (w - z0) ** 2 + 0.5 * s * w ** 2, color=BLUE, lw=2, label="Ridge, $z=0{,}8$")
    ax.plot(w, 0.5 * (w - z0) ** 2 + s * np.abs(w), color=ORANGE, lw=2, label="Lasso, $z=0{,}8$")
    ax.scatter([z0 / (1 + s)], [0.5 * (z0 / 2 - z0) ** 2 + 0.5 * (z0 / 2) ** 2], color=BLUE, zorder=4)
    ax.scatter([0], [0.5 * z0 ** 2], color=ORANGE, zorder=4)
    ax.annotate("минимум ровно в 0:\nизлом выигрывает", (0, 0.32), xytext=(1.25, 0.62),
                color=ORANGE, arrowprops=dict(arrowstyle="->", color=ORANGE))
    ax.annotate("минимум 0,4", (0.4, 0.32), xytext=(1.25, 0.12), color=BLUE,
                arrowprops=dict(arrowstyle="->", color=BLUE))
    ax.set(title="Целевая функция по весу", xlabel="вес $w$", ylabel="значение", ylim=(0, 2.2), xlim=(-1, 3))
    ax.legend(loc="upper left", fontsize=9.5)
    save(fig, "shrinkage")


# --- 7. пути коэффициентов ---------------------------------------------------
def fig_paths():
    X, y, true_w = make_dataset()
    Xs = StandardScaler().fit_transform(X[:30])
    yc = y[:30] - y[:30].mean()
    alphas = np.logspace(-3, 2, 60)
    fig, axes = plt.subplots(1, 2, figsize=(7.6, 3.4), sharey=True, layout="constrained")
    colors = {0: BLUE, 1: ORANGE, 2: GREEN, 3: RED}
    names = {0: "$x_1$ (истина 3)", 1: "$x_2$ (истина −2)", 2: "$x_3$ (истина 1,5)",
             3: "$x_4\\approx x_1$ (истина 0)"}
    for ax, cls, title in zip(axes, (Ridge, Lasso), ("Ridge: веса сжимаются", "Lasso: веса обнуляются")):
        coefs = np.array([cls(alpha=a, fit_intercept=False).fit(Xs, yc).coef_ for a in alphas])
        for j in range(coefs.shape[1]):
            ax.plot(alphas, coefs[:, j], color=colors.get(j, LIGHT), lw=2 if j in colors else 1.2,
                    label=names.get(j) if cls is Ridge else None, zorder=3 if j in colors else 2)
        ax.set(title=title, xscale="log", xlabel="alpha (логарифмическая шкала)")
        ax.axhline(0, color=GRAY, lw=1)
    axes[0].set_ylabel("вес при стандартизованном признаке")
    axes[0].set_ylim(-2.9, 4.3)
    axes[0].legend(fontsize=8, loc="upper center", ncols=2)
    save(fig, "paths")


# --- 8. сравнение моделей и выбор силы штрафа -----------------------------------
def fig_compare():
    X, y, true_w = make_dataset()
    Xtr, Xva = X[:30], X[30:60]
    ytr, yva = y[:30], y[30:60]
    alphas = np.logspace(-3, 3, 40)
    fig, axes = plt.subplots(1, 2, figsize=(7.8, 3.5), gridspec_kw={"width_ratios": [1.35, 1]},
                             layout="constrained")
    ax = axes[1]
    fitted = {"МНК": make_pipeline(StandardScaler(), LinearRegression()).fit(Xtr, ytr)}
    for name, cls, color in (("Ridge", Ridge, BLUE), ("Lasso", Lasso, ORANGE)):
        errs = [rmse(yva, make_pipeline(StandardScaler(), cls(alpha=a)).fit(Xtr, ytr).predict(Xva))
                for a in alphas]
        k = int(np.argmin(errs))
        ax.plot(alphas, errs, color=color, lw=2, label=name)
        ax.scatter(alphas[k], errs[k], color=color, s=60, zorder=4)
        fitted[name] = make_pipeline(StandardScaler(), cls(alpha=alphas[k])).fit(Xtr, ytr)
    ax.axhline(rmse(yva, fitted["МНК"].predict(Xva)), color=RED, ls="--", lw=1.4, label="МНК")
    ax.set(title="Ошибка на проверке", xscale="log", xlabel="alpha", ylabel="RMSE")
    ax.legend(fontsize=9.5)
    ax = axes[0]
    idx = np.arange(12)
    width = 0.2
    ax.bar(idx - 1.5 * width, true_w, width, color=GRAY, label="истина")
    for shift, (name, color) in zip((-0.5, 0.5, 1.5), (("МНК", RED), ("Ridge", BLUE), ("Lasso", ORANGE))):
        ax.bar(idx + shift * width, fitted[name][-1].coef_, width, color=color, label=name)
    ax.axhline(0, color="black", lw=0.8)
    ax.set(title="Веса моделей", xlabel="номер признака", xticks=idx, xticklabels=idx + 1)
    ax.legend(fontsize=8.5, ncols=2)
    save(fig, "compare")


if __name__ == "__main__":
    MEDIA.mkdir(exist_ok=True)
    fig_fit()
    path, losses = fig_surface()
    print("GD после 1 шага:", path[1], "после 300:", path[-1], "loss", losses[-1])
    fig_pitfalls()
    print("переобучение:", fig_overfit())
    fig_geometry()
    fig_shrink()
    fig_paths()
    fig_compare()
