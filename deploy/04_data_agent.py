"""Data Agent agent_operacje_northwind: instrukcje, 2 zrodla, few-shoty T-SQL sprawdzone na SQL endpoint."""
from __future__ import annotations

import json
import struct
import uuid

import pyodbc
import requests

from common import AGENT, API, LAKEHOUSE, MODEL, get_definition, h, load_state, part, save_state, token, upsert_item

BASE = "https://developer.microsoft.com/json-schemas/fabric/item/dataAgent/definition"
SCHEMA_AGENT = f"{BASE}/dataAgent/2.1.0/schema.json"
SCHEMA_STAGE = f"{BASE}/stageConfiguration/1.0.0/schema.json"
SCHEMA_SOURCE = f"{BASE}/dataSource/1.0.0/schema.json"
SCHEMA_FEWSHOTS = f"{BASE}/fewShots/1.0.0/schema.json"

INSTRUCTIONS = """Jesteś asystentem analitycznym dla działu operacji i IT sklepu internetowego z dostawą zakupów spożywczych do domu.
Odpowiadasz po polsku, krótko, zaczynając od liczby lub wniosku, a potem podajesz 2-3 najważniejsze szczegóły.

Dane są syntetyczne i przygotowane na potrzeby demonstracji. Jeśli ktoś pyta o prawdziwe wyniki firmy, powiedz, że to demo na danych fikcyjnych.

Dzisiejsza data w scenariuszu to 28.10.2026 (środa). Nie używaj GETDATE() ani TODAY(). "Wczoraj" to 27.10.2026, "ostatni tydzień" to pełny tydzień 19.10-25.10.2026, "ostatnie 7 dni" to 21.10-27.10.2026, "ten miesiąc" to październik 2026. Dane obejmują 03.08-27.10.2026.

Wybór źródła:
- Pytania o wskaźniki (punktualność, braki, zamienniki, odpisy, kompletność ładowań) kieruj do modelu semantycznego sm_northwind_operacje i używaj gotowych miar, np. [Punktualność %], [Udział braków %], [Linie niekompletne %], [Odpisy wartość], [Ładowania niepełne].
- Pytania o listy szczegółów (konkretne kursy, komunikaty błędów, które tabele się nie załadowały) kieruj do lakehouse lh_northwind_demo.

Definicje:
- Punktualność to odsetek dostaw doręczonych przed końcem wybranego dwugodzinnego okna. Liczymy ją tylko z dostaw, które mają czas doręczenia (w_oknie nie jest NULL). Zamówienia ze statusem "Brak danych z TMS" to luka w danych, a nie spóźnienie. Zawsze o tym wspominaj, jeśli występują w zakresie pytania.
- Spóźnienie to dostawa po końcu okna. Przyczyny: KOREK, WYJAZD (opóźniony wyjazd z magazynu), DOJAZD (długi dojazd z magazynu do miasta), AWARIA, POGODA, KLIENT, ADRES.
- Status linii zamówienia: Kompletna, Zamiennik, Częściowa, Brak. Linie niekompletne to wszystko poza Kompletna.
- Odpisy liczymy w cenie zakupu. Odpisy % sprzedaży to wartość odpisów do wartości wydanego towaru.
- Log ładowań: data_biznesowa to dzień, którego dotyczą dane. Ładowanie odbywa się następnej nocy. Status inny niż Sukces oznacza problem.

Centrum dystrybucyjne Lublin obsługuje Lublin i Zamość. Magazyn Rzeszów obsługuje Rzeszów i Przemyśl, magazyn Olsztyn obsługuje Olsztyn i Elbląg.
Procenty podawaj z jednym miejscem po przecinku, kwoty w zł bez groszy. Jeśli nie masz danych, powiedz to wprost i nie zgaduj."""

LAKEHOUSE_HINT = ("Tabele dim_* to słowniki, fact_* to operacje, it_* to log ładowań i kontrole jakości danych. "
                  "fact_zamowienie łączy się z dim_miasto po miasto_id i z dim_okno po okno_id. "
                  "fact_linia_zamowienia łączy się z fact_zamowienie po zamowienie_id i z dim_produkt po sku_id. "
                  "dim_produkt łączy się z dim_dostawca po dostawca_id. Kolumna w_oknie jest typu bit i może być NULL.")
MODEL_HINT = ("Model z gotowymi miarami KPI. Tabela Data ma kolumny miesiac (nazwa polska małą literą), tydzien i data. "
              "Do filtrowania miast używaj Miasto[miasto], magazynów Magazyn[magazyn], dostawców Dostawca[dostawca].")

FEWSHOTS = [
    ("Które miasto miało najniższą punktualność w zeszłym tygodniu?",
     """SELECT m.miasto,
       CAST(100.0 * SUM(CASE WHEN z.w_oknie = 1 THEN 1 ELSE 0 END) / COUNT(*) AS DECIMAL(5,1)) AS punktualnosc_pct,
       COUNT(*) AS dostawy
FROM dbo.fact_zamowienie z
JOIN dbo.dim_miasto m ON m.miasto_id = z.miasto_id
WHERE z.data_dostawy BETWEEN '2026-10-19' AND '2026-10-25' AND z.w_oknie IS NOT NULL
GROUP BY m.miasto
ORDER BY punktualnosc_pct ASC;"""),
    ("W których oknach Rzeszów spóźnia się najczęściej i z jakiego powodu?",
     """SELECT o.okno,
       CAST(100.0 * SUM(CASE WHEN z.w_oknie = 0 THEN 1 ELSE 0 END) / COUNT(*) AS DECIMAL(5,1)) AS spoznione_pct,
       SUM(CASE WHEN z.przyczyna_spoznienia_kod = 'KOREK' THEN 1 ELSE 0 END) AS przez_korki,
       SUM(CASE WHEN z.w_oknie = 0 THEN 1 ELSE 0 END) AS spoznione
FROM dbo.fact_zamowienie z
JOIN dbo.dim_okno o ON o.okno_id = z.okno_id
WHERE z.miasto_id = 'RZE' AND z.w_oknie IS NOT NULL
GROUP BY o.okno, o.godzina_od
ORDER BY spoznione_pct DESC;"""),
    ("Którzy dostawcy mieli najwyższy udział braków w październiku?",
     """SELECT TOP 5 d.dostawca,
       CAST(100.0 * SUM(CASE WHEN l.status_linii = 'Brak' THEN 1 ELSE 0 END) / COUNT(*) AS DECIMAL(5,2)) AS braki_pct,
       CAST(100.0 * SUM(CASE WHEN l.status_linii <> 'Kompletna' THEN 1 ELSE 0 END) / COUNT(*) AS DECIMAL(5,2)) AS niekompletne_pct,
       COUNT(*) AS linie
FROM dbo.fact_linia_zamowienia l
JOIN dbo.fact_zamowienie z ON z.zamowienie_id = l.zamowienie_id
JOIN dbo.dim_produkt p ON p.sku_id = l.sku_id
JOIN dbo.dim_dostawca d ON d.dostawca_id = p.dostawca_id
WHERE z.data_dostawy BETWEEN '2026-10-01' AND '2026-10-27'
GROUP BY d.dostawca
ORDER BY braki_pct DESC;"""),
    ("Ile odpisaliśmy w magazynie w Rzeszowie 7 października i dlaczego?",
     """SELECT r.przyczyna_odpisu, p.kategoria,
       SUM(o.ilosc) AS sztuki,
       CAST(SUM(o.wartosc_kosztowa) AS DECIMAL(12,0)) AS wartosc_zl
FROM dbo.fact_odpis o
JOIN dbo.dim_przyczyna_odpisu r ON r.przyczyna_odpisu_kod = o.przyczyna_odpisu_kod
JOIN dbo.dim_produkt p ON p.sku_id = o.sku_id
WHERE o.magazyn_id = 'RZE' AND o.data = '2026-10-07'
GROUP BY r.przyczyna_odpisu, p.kategoria
ORDER BY wartosc_zl DESC;"""),
    ("Czy dane za wczoraj są kompletne?",
     """SELECT system_zrodlowy, tabela, status, proba, wiersze_zaladowane, wiersze_oczekiwane,
       koniec_ladowania, komunikat_bledu
FROM dbo.it_log_ladowan
WHERE data_biznesowa = '2026-10-27'
ORDER BY CASE WHEN status = 'Sukces' THEN 1 ELSE 0 END, system_zrodlowy, tabela;"""),
    ("Które kontrole jakości danych nie przeszły w ostatnich 7 dniach?",
     """SELECT data_biznesowa, system_zrodlowy, tabela, kontrola, wynik, bledne_wiersze
FROM dbo.it_kontrola_jakosci
WHERE data_biznesowa BETWEEN '2026-10-21' AND '2026-10-27' AND wynik <> 'Zaliczona'
ORDER BY data_biznesowa DESC;"""),
    ("Dlaczego pod koniec września spadła punktualność porannych dostaw z centrum Lublin?",
     """SELECT k.data,
       COUNT(*) AS kursy,
       SUM(CASE WHEN k.opoznienie_wyjazdu_min > 15 THEN 1 ELSE 0 END) AS opoznione_wyjazdy,
       CAST(AVG(CAST(k.opoznienie_wyjazdu_min AS FLOAT)) AS DECIMAL(5,1)) AS srednie_opoznienie_wyjazdu_min
FROM dbo.fact_kurs k
JOIN dbo.dim_miasto m ON m.miasto_id = k.miasto_id
WHERE m.magazyn_id = 'LUB' AND k.data BETWEEN '2026-09-21' AND '2026-10-09'
  AND DATEPART(HOUR, k.planowany_wyjazd) < 9
GROUP BY k.data
ORDER BY k.data;"""),
]


def sql_conn(server: str) -> pyodbc.Connection:
    tk = token("https://database.windows.net/").encode("utf-16-le")
    attrs = struct.pack(f"<I{len(tk)}s", len(tk), tk)
    return pyodbc.connect(f"Driver={{ODBC Driver 18 for SQL Server}};Server={server},1433;Database={LAKEHOUSE};"
                          "Encrypt=yes;TrustServerCertificate=no", attrs_before={1256: attrs})


def check_fewshots(server: str) -> None:
    cn = sql_conn(server)
    for q, sql in FEWSHOTS:
        rows = cn.cursor().execute(sql).fetchall()
        assert rows, f"pusty wynik: {q}"
        print(f"OK {len(rows):>3} wierszy | {q}\n     {tuple(rows[0])}")


def element(name: str, kind: str) -> dict:
    return {"display_name": name, "type": kind, "is_selected": True, "children": []}


def main() -> None:
    s = load_state()
    ws = s["workspace_id"]
    check_fewshots(s["sql_endpoint"])

    lh_tables = sorted(t["name"] for t in requests.get(
        f"{API}/workspaces/{ws}/lakehouses/{s['lakehouse_id']}/tables", headers=h()).json()["data"])
    import importlib.util
    from common import ROOT
    spec = importlib.util.spec_from_file_location("sm", ROOT / "deploy" / "02_semantic_model.py")
    sm = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sm)

    sources = [
        (LAKEHOUSE, "lakehouse_tables", s["lakehouse_id"], LAKEHOUSE_HINT, "Szczegółowe dane operacyjne i log IT",
         [element(t, "lakehouse_tables.table") for t in lh_tables]),
        (MODEL, "semantic_model", s["semantic_model_id"], MODEL_HINT, "Model z miarami KPI",
         [element(t, "semantic_model.table") for t in sm.TABLES]),
    ]
    parts = [part("Files/Config/data_agent.json", {"$schema": SCHEMA_AGENT}),
             part("Files/Config/draft/stage_config.json", {"$schema": SCHEMA_STAGE, "aiInstructions": INSTRUCTIONS})]
    for name, typ, aid, hint, desc, els in sources:
        folder = f"Files/Config/draft/{typ.replace('_', '-')}-{name}"
        parts.append(part(f"{folder}/datasource.json", {
            "$schema": SCHEMA_SOURCE, "artifactId": aid, "workspaceId": ws, "displayName": name, "type": typ,
            "userDescription": desc, "dataSourceInstructions": hint, "elements": els}))
        if typ == "lakehouse_tables":
            parts.append(part(f"{folder}/fewshots.json", {"$schema": SCHEMA_FEWSHOTS, "fewShots": [
                {"id": str(uuid.uuid5(uuid.NAMESPACE_URL, q)), "question": q, "query": sql} for q, sql in FEWSHOTS]}))

    aid = upsert_item(ws, AGENT, "DataAgent", parts)
    s["data_agent_id"] = aid
    save_state(s)
    back = get_definition(ws, aid)
    for p in sorted(back):
        extra = ""
        if p.endswith("datasource.json"):
            extra = f"{len(json.loads(back[p]).get('elements', []))} elementów"
        elif p.endswith("fewshots.json"):
            extra = f"{len(json.loads(back[p]).get('fewShots', []))} few-shotów"
        elif p.endswith("stage_config.json"):
            extra = f"instrukcje {len(json.loads(back[p]).get('aiInstructions', ''))} znaków"
        print(" ", p, extra)
    print(f"agent {aid}")


if __name__ == "__main__":
    main()
