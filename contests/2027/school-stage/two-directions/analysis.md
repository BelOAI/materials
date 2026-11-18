Сложим координаты перемещений. Получим систему:

$$\begin{cases}2\alpha+3\beta=2{,}6,\\5\alpha+\beta=3{,}9.\end{cases}$$

Из второго уравнения $\beta=3{,}9-5\alpha$. Подставим в первое:

$$2\alpha+3(3{,}9-5\alpha)=2{,}6,$$

$$-13\alpha=-9{,}1,\qquad \alpha=0{,}7.$$

Подставим результат во второе уравнение: $\beta=3{,}9-5\cdot0{,}7=0{,}4$. Оба коэффициента лежат в отрезке $[0,1]$. **Ответ: 0,7.**

<details><summary>Код Python</summary>

```python
target = (2.6, 3.9)
u, v = (2, 5), (3, 1)

det = u[0] * v[1] - v[0] * u[1]
alpha = (target[0] * v[1] - v[0] * target[1]) / det
print(f"{alpha:.1f}".replace(".", ","))
```

</details>
