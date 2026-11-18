Сначала найдём число пикселей: в каждой из 1024 строк по 1024 пикселя. Каждый из них занимает 4 байта, значит, объём равен

$$1024 \cdot 1024 \cdot 4 = 4\,194\,304 \text{ байта}.$$

**Ответ: 4194304.**

<details><summary>Код Python</summary>

```python
width = height = 1024
bytes_per_pixel = 4
print(width * height * bytes_per_pixel)
```

</details>
