"""Создаёт тестовые данные: каталог запчастей и «грязный» складской список клиента.

Данные вымышленные (реальных данных компании у нас нет), но ошибки в них такие, как в жизни:
разный регистр, сокращения, артикулы без дефисов, опечатки, повторы одной позиции,
позиции, которых нет в каталоге.

Запуск: .venv/bin/python generate_data.py
Результат: data/catalog.xlsx, data/client_stock.xlsx и data/truth.csv (эталон для проверки точности).
"""

import random
from pathlib import Path

import pandas as pd

random.seed(42)
OUT = Path(__file__).with_name("data")
OUT.mkdir(exist_ok=True)

# Модели техники: (как пишут в каталоге, префикс артикула)
MODELS = [
    ("МТЗ-80", "70"), ("МТЗ-82", "72"), ("МТЗ-1221", "122"), ("Беларус-892", "89"),
    ("К-700", "700"), ("К-744", "744"), ("ДТ-75", "75"), ("Т-150К", "150"),
    ("John Deere 8320R", "RE"), ("John Deere 6155M", "AL"), ("Claas Lexion 760", "CL"),
    ("Claas Tucano 450", "CT"), ("Енисей-1200", "1200"), ("Нива СК-5", "54"), ("Дон-1500Б", "1500"),
]

# Типы запчастей: (название, код узла)
PARTS = [
    ("Фильтр масляный", "1012"), ("Фильтр топливный тонкой очистки", "1117"), ("Фильтр воздушный", "1109"),
    ("Фильтр гидравлический", "4605"), ("Ремень вентилятора", "1308"), ("Ремень генератора", "3701"),
    ("Насос водяной в сборе", "1307"), ("Насос топливный подкачивающий", "1106"), ("Стартер", "3708"),
    ("Генератор", "3771"), ("Диск сцепления ведомый", "1601"), ("Корзина сцепления", "1602"),
    ("Подшипник выжимной", "1604"), ("Прокладка ГБЦ", "1003"), ("Поршень с кольцами", "1004"),
    ("Вкладыши коренные", "1005"), ("Радиатор водяной", "1301"), ("Термостат", "1306"),
    ("Форсунка топливная", "1112"), ("Тяга рулевая", "3003"), ("Наконечник рулевой тяги", "3414"),
    ("Цилиндр гидравлический", "8603"), ("Шланг РВД", "8604"), ("Палец гусеницы", "2201"),
    ("Нож режущего аппарата", "5101"), ("Сегмент ножа", "5102"), ("Палец режущего аппарата", "5103"),
    ("Цепь элеватора", "5205"), ("Звёздочка ведущая", "5206"), ("Вариатор барабана", "5301"),
    ("Решето верхнее", "5401"), ("Ремень ходовой части", "5501"), ("Подшипник ступицы", "3103"),
    ("Сальник коленвала", "1008"), ("Датчик давления масла", "3829"),
]

catalog = []
used = set()
for model, prefix in MODELS:
    for name, node in random.sample(PARTS, k=random.randint(25, 34)):
        if prefix.isalpha():  # импортная техника: буквенно-цифровой артикул
            art = f"{prefix}{random.randint(100000, 999999)}"
        else:
            art = f"{prefix}-{node}{random.randint(10, 99)}0"
        if art in used:
            continue
        used.add(art)
        catalog.append({"id": len(catalog) + 1, "article": art, "name": f"{name} {model}",
                        "unit": "шт", "brand_model": model})
cat = pd.DataFrame(catalog)

# ---------- Искажения, как в реальных складских таблицах ----------
ABBR = [("Фильтр", "Ф-р"), ("масляный", "масл."), ("топливный", "топл."), ("гидравлический", "гидр."),
        ("в сборе", "в сб."), ("тонкой очистки", "т/о"), ("вентилятора", "вент."), ("сцепления", "сцепл."),
        ("Подшипник", "Подш."), ("коренные", "корен."), ("режущего аппарата", "реж. апп."), ("Цилиндр", "Ц-р")]
JUNK = ["Перчатки рабочие х/б", "Масло моторное М-10Г2к 20л", "Солидол Ж 2кг", "Лампа Н4 24В",
        "Ветошь обтирочная, кг", "Огнетушитель ОП-5", "Краска эмаль зелёная 2.7кг", "Хомут червячный 16-25",
        "Изолента ПВХ синяя", "Антифриз G11 10л", "Болт М12х40 оцинк.", "Ведро оцинкованное 12л"]


def typo(s: str) -> str:
    """Одна случайная опечатка: перестановка двух соседних букв."""
    letters = [i for i in range(len(s) - 1) if s[i].isalpha() and s[i + 1].isalpha()]
    if not letters:
        return s
    i = random.choice(letters)
    return s[:i] + s[i + 1] + s[i] + s[i + 2:]


def dirty_name(name: str, model: str) -> str:
    n = name
    for full, short in random.sample(ABBR, k=len(ABBR)):
        if full in n and random.random() < 0.6:
            n = n.replace(full, short)
    if random.random() < 0.5:  # модель пишут как придётся: «МТЗ-80» -> «мтз80», «МТЗ 80»
        n = n.replace(model, random.choice([model.replace("-", ""), model.replace("-", " "), model.lower()]))
    if random.random() < 0.3:
        n = n.lower()
    if random.random() < 0.2:
        n = typo(n)
    if random.random() < 0.15:
        n += random.choice([" (оригинал)", " новый", " !!!", " Беларус"])
    return n


def dirty_article(art: str) -> str:
    r = random.random()
    if r < 0.30:
        return art
    if r < 0.55:
        return art.replace("-", "")  # без дефиса
    if r < 0.65:
        return "арт. " + art.lower()
    if r < 0.75:
        return art.replace("-", " ")
    if r < 0.85:  # опечатка в одной цифре
        digits = [i for i, ch in enumerate(art) if ch.isdigit()]
        i = random.choice(digits)
        return art[:i] + str((int(art[i]) + random.randint(1, 8)) % 10) + art[i + 1:]
    return ""  # артикул не указан


rows, truth = [], []
picked = cat.sample(frac=0.85, random_state=1)
for _, p in picked.iterrows():
    copies = 2 if random.random() < 0.12 else 1  # часть позиций заведена на складе дважды
    for _ in range(copies):
        rows.append({"Артикул": dirty_article(p["article"]),
                     "Наименование": dirty_name(p["name"], p["brand_model"]),
                     "Ед.": random.choice(["шт", "шт.", "ШТ", "штук"]),
                     "Остаток": random.randint(0, 40)})
        truth.append(int(p["id"]))
for _ in range(60):  # то, чего нет в каталоге запчастей
    rows.append({"Артикул": "", "Наименование": random.choice(JUNK), "Ед.": "шт", "Остаток": random.randint(1, 50)})
    truth.append(0)

order = list(range(len(rows)))
random.shuffle(order)
stock = pd.DataFrame([rows[i] for i in order])
stock.insert(0, "Строка", range(1, len(stock) + 1))
truth_df = pd.DataFrame({"Строка": stock["Строка"], "catalog_id": [truth[i] for i in order]})

cat.rename(columns={"id": "ID", "article": "Артикул", "name": "Наименование", "unit": "Ед.",
                    "brand_model": "Модель техники"}).to_excel(OUT / "catalog.xlsx", index=False)
stock.to_excel(OUT / "client_stock.xlsx", index=False)
truth_df.to_csv(OUT / "truth.csv", index=False)
print(f"каталог: {len(cat)} позиций; склад клиента: {len(stock)} строк")
