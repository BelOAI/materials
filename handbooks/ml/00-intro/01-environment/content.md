## Подготовка среды

Первое занятие можно выполнить без установки дополнительных библиотек: его данные находятся внутри ноутбука.

### Google Colab

Скачайте ноутбук урока и откройте его в [Google Colab](https://colab.research.google.com/). Выполняйте ячейки сверху вниз сочетанием Shift+Enter. Перед проверкой решения перезапустите сеанс и выполните всё по порядку.

Если параграф содержит файлы данных, загрузите их в рабочую папку Colab рядом с ноутбуком.

### Локально: Python 3.14 и Jupyter

Установите Python 3.14. В Linux или macOS создайте и активируйте отдельную среду:

```bash
python3.14 -m venv .venv
source .venv/bin/activate
```

В Windows PowerShell:

```powershell
py -3.14 -m venv .venv
.venv\Scripts\Activate.ps1
```

Установите Jupyter в активированной среде:

```bash
python -m pip install jupyter
```

Скачайте [список библиотек](requirements.txt) и выполните в активированной среде:

```bash
python -m pip install -r requirements.txt
jupyter notebook
```

### Библиотеки в Colab

Для следующих занятий в Colab загрузите `requirements.txt` и выполните `%pip install -r requirements.txt` в отдельной ячейке. Если среда попросит, перезапустите сеанс. Установка требует интернета; учебные примеры работают на обычном процессоре без скачивания внешних моделей.
