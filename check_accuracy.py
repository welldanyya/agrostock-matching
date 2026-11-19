"""Проверка точности: сравнивает результат с эталоном (data/truth.csv), где заранее известен правильный ответ.
Запуск после match.py: .venv/bin/python check_accuracy.py
"""
import pandas as pd

r = pd.read_csv("result/_for_check.csv")
t = pd.read_csv("data/truth.csv")
m = r.merge(t, on="Строка")
m["ID каталога"] = pd.to_numeric(m["ID каталога"], errors="coerce").fillna(0).astype(int)
for st in ["Точно", "Вероятно"]:
    a = m[m.status == st]
    print(f"{st}: {len(a)} строк, верно сопоставлено {(a['ID каталога'] == a.catalog_id).sum()}")
nf = m[m.status == "Не найдено"]
print(f"Не найдено: {len(nf)}, из них действительно нет в каталоге: {(nf.catalog_id == 0).sum()}")
print(f"На ручную проверку: {(m.status == 'Проверить вручную').sum()}")
v = t[t.catalog_id > 0].catalog_id.value_counts()
print(f"Настоящих дублей в данных: {(v > 1).sum()}")
