"""Сопоставление складской номенклатуры клиента с единым каталогом + поиск дублей.

Шаги для каждой строки склада:
1. Артикул: приводим к одному виду (без пробелов, дефисов, «арт.», регистра) и ищем точное совпадение.
   Если артикул совпал, а название совсем другое — не верим, отправляем на ручную проверку.
2. Название: раскрываем сокращения (ф-р -> фильтр, масл. -> масляный), выравниваем запись моделей
   (МТЗ-80 / мтз 80 / мтз80 -> мтз80) и ищем самые похожие позиции каталога нечётким сравнением,
   которое терпит опечатки.
3. Артикул с опечаткой в одной цифре + похожее название — тоже считаем совпадением.
4. Уверенность: «Точно» / «Вероятно» — сопоставлено автоматически; «Проверить вручную» — показываем
   3 лучших кандидата; «Не найдено» — позиции нет в каталоге запчастей.
Затем строки, сопоставленные с одной позицией каталога, — это дубли: их остатки складываем.

Запуск: .venv/bin/python match.py  ->  result/matching_result.xlsx
"""

import re
from pathlib import Path

import pandas as pd
from rapidfuzz import fuzz, process
from rapidfuzz.distance import Levenshtein

BASE = Path(__file__).parent
OUT = BASE / "result"
OUT.mkdir(exist_ok=True)

AUTO_SCORE = 90      # от этого сходства названия сопоставляем автоматически...
AUTO_MARGIN = 4      # ...если лучший кандидат заметно лучше второго (иначе путаем МТЗ-80 и МТЗ-82)
REVIEW_SCORE = 75    # ниже — считаем, что позиции нет в каталоге
NAME_CHECK = 60      # артикул совпал, но названия похожи меньше чем на 60% — подозрительно

ABBR = {"ф-р": "фильтр", "масл": "масляный", "топл": "топливный", "гидр": "гидравлический",
        "сб": "сборе", "т/о": "тонкой очистки", "вент": "вентилятора", "сцепл": "сцепления",
        "подш": "подшипник", "корен": "коренные", "реж": "режущего", "апп": "аппарата", "ц-р": "цилиндр"}
NOISE = r"\b(оригинал|новый|новая|шт)\b|!+"


def norm_article(a) -> str:
    a = str(a or "").lower().replace("арт.", "").replace("арт", "")
    return re.sub(r"[^0-9a-zа-я]", "", a)


def norm_name(s) -> str:
    s = str(s or "").lower().replace("ё", "е")
    s = re.sub(NOISE, " ", s)
    for short, full in ABBR.items():
        s = re.sub(rf"(?<![\w-]){re.escape(short)}\.?(?![\w-])", full, s)
    s = re.sub(r"([a-zа-я])[\s-]+(\d)", r"\1\2", s)   # мтз-80 / мтз 80 -> мтз80
    s = re.sub(r"[^\w\s/]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


cat = pd.read_excel(BASE / "data/catalog.xlsx", dtype=str)
stock = pd.read_excel(BASE / "data/client_stock.xlsx", dtype=str).fillna("")
stock["Остаток"] = pd.to_numeric(stock["Остаток"], errors="coerce").fillna(0).astype(int)

cat["art_n"] = cat["Артикул"].map(norm_article)
cat["name_n"] = cat["Наименование"].map(norm_name)
by_article = dict(zip(cat["art_n"], cat.index))
names = cat["name_n"].tolist()


def match_row(row) -> dict:
    art = norm_article(row["Артикул"])
    name = norm_name(row["Наименование"])
    top = process.extract(name, names, scorer=fuzz.token_set_ratio, limit=3)
    cands = [(cat.index[i], round(score)) for _, score, i in top]
    best_i, best = cands[0]
    second = cands[1][1] if len(cands) > 1 else 0

    if art and art in by_article:
        i = by_article[art]
        sim = fuzz.token_set_ratio(name, cat.at[i, "name_n"])
        if sim >= NAME_CHECK:
            return {"i": i, "status": "Точно", "how": "артикул совпал", "score": 100, "cands": cands}
        return {"i": None, "status": "Проверить вручную", "how": f"артикул совпал, но название другое ({sim:.0f}%)",
                "score": sim, "cands": [(i, round(sim))] + cands[:2]}

    if art:  # опечатка в одной-двух цифрах артикула у одного из кандидатов по названию
        for i, score in cands:
            if Levenshtein.distance(art, cat.at[i, "art_n"]) <= 1 and score >= REVIEW_SCORE:
                return {"i": i, "status": "Вероятно", "how": "опечатка в артикуле, название совпало",
                        "score": score, "cands": cands}

    if best >= AUTO_SCORE and best - second >= AUTO_MARGIN:
        return {"i": best_i, "status": "Вероятно", "how": "похожее название", "score": best, "cands": cands}
    if best >= REVIEW_SCORE:
        why = "несколько похожих позиций" if best - second < AUTO_MARGIN else "название похоже не полностью"
        return {"i": None, "status": "Проверить вручную", "how": why, "score": best, "cands": cands}
    return {"i": None, "status": "Не найдено", "how": "нет в каталоге запчастей", "score": best, "cands": cands}


res = stock.apply(match_row, axis=1, result_type="expand")
out = pd.concat([stock, res], axis=1)


def cat_field(i, col):
    return cat.at[i, col] if pd.notna(i) and i is not None else ""


out["ID каталога"] = out["i"].map(lambda i: cat_field(i, "ID"))
out["Артикул каталога"] = out["i"].map(lambda i: cat_field(i, "Артикул"))
out["Наименование каталога"] = out["i"].map(lambda i: cat_field(i, "Наименование"))
out["Кандидаты"] = out["cands"].map(lambda cs: "\n".join(
    f"{cat.at[i, 'Артикул']} — {cat.at[i, 'Наименование']} ({s}%)" for i, s in cs))

matched = out[out["status"].isin(["Точно", "Вероятно"])]
dup_ids = matched["ID каталога"].value_counts()
dup_ids = dup_ids[dup_ids > 1].index
dups = matched[matched["ID каталога"].isin(dup_ids)].sort_values(["ID каталога", "Строка"])
dup_summary = (dups.groupby(["ID каталога", "Артикул каталога", "Наименование каталога"], as_index=False)
               .agg(**{"Строк на складе": ("Строка", "count"),
                       "Номера строк": ("Строка", lambda s: ", ".join(map(str, s))),
                       "Как записано": ("Наименование", lambda s: " | ".join(s)),
                       "Общий остаток": ("Остаток", "sum")}))

# ---------- Сохранение ----------
cols = ["Строка", "Артикул", "Наименование", "Остаток", "status", "how", "score",
        "ID каталога", "Артикул каталога", "Наименование каталога"]
ren = {"Артикул": "Артикул (склад)", "Наименование": "Наименование (склад)", "status": "Уверенность",
       "how": "Как найдено", "score": "Сходство, %"}
counts = out["status"].value_counts()
total = len(out)
summary = pd.DataFrame([
    ("Строк в складском файле клиента", total),
    ("Позиций в каталоге", len(cat)),
    ("Сопоставлено автоматически: «Точно» (по артикулу)", int(counts.get("Точно", 0))),
    ("Сопоставлено автоматически: «Вероятно» (название / опечатка в артикуле)", int(counts.get("Вероятно", 0))),
    ("На ручную проверку (есть 2–3 кандидата)", int(counts.get("Проверить вручную", 0))),
    ("Не найдено в каталоге (не запчасти: расходники, хозтовары)", int(counts.get("Не найдено", 0))),
    ("Позиций каталога, заведённых на складе дважды и более (дубли)", len(dup_summary)),
    ("Лишних строк-дублей можно объединить", int(dup_summary["Строк на складе"].sum() - len(dup_summary))),
], columns=["Показатель", "Значение"])

path = OUT / "matching_result.xlsx"
with pd.ExcelWriter(path, engine="openpyxl") as xw:
    summary.to_excel(xw, sheet_name="Отчёт", index=False)
    matched[cols].rename(columns=ren).to_excel(xw, sheet_name="Сопоставлено", index=False)
    out[out["status"] == "Проверить вручную"][cols[:7] + ["Кандидаты"]].rename(columns=ren).to_excel(
        xw, sheet_name="Проверить вручную", index=False)
    out[out["status"] == "Не найдено"][["Строка", "Артикул", "Наименование", "Остаток"]].to_excel(
        xw, sheet_name="Не найдено", index=False)
    dup_summary.to_excel(xw, sheet_name="Дубли", index=False)
out[["Строка", "status", "ID каталога"]].to_csv(OUT / "_for_check.csv", index=False)
print(summary.to_string(index=False))
print("сохранено:", path)

# ---------- Оформление: ширина колонок, перенос текста, цвет уверенности ----------
from openpyxl import load_workbook  # noqa: E402
from openpyxl.styles import Alignment, Font, PatternFill  # noqa: E402

COLORS = {"Точно": "D9F2E3", "Вероятно": "FFF4CC", "Проверить вручную": "FDE2CF", "Не найдено": "F2F2F2"}
wb = load_workbook(path)
for ws in wb.worksheets:
    for c in ws[1]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor="2F5D50")
        c.alignment = Alignment(wrap_text=True, vertical="center")
    for col in ws.columns:
        longest = max(len(str(c.value or "").split("\n")[0]) for c in col)
        ws.column_dimensions[col[0].column_letter].width = min(max(10, longest + 2), 60)
    headers = [c.value for c in ws[1]]
    for row in ws.iter_rows(min_row=2):
        for c in row:
            c.alignment = Alignment(wrap_text=True, vertical="top")
        if "Уверенность" in headers:
            st = row[headers.index("Уверенность")].value
            if st in COLORS:
                for c in row:
                    c.fill = PatternFill("solid", fgColor=COLORS[st])
    ws.freeze_panes = "A2"
wb["Отчёт"].column_dimensions["A"].width = 72
wb.save(path)
