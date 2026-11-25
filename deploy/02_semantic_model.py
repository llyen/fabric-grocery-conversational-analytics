"""Model semantyczny Direct Lake sm_northwind_operacje nad lh_northwind_demo."""
from __future__ import annotations

import json
import time
import uuid

import requests

from common import LAKEHOUSE, MODEL, ROOT, h, load_state, part, save_state, upsert_item

SCHEMAS = json.loads((ROOT / "data" / "_schemas.json").read_text(encoding="utf-8"))
PBI = "https://api.powerbi.com/v1.0/myorg"
PBI_RES = "https://analysis.windows.net/powerbi/api"

TYPE_MAP = {"string": "string", "bool": "boolean", "date32[day]": "dateTime", "int64": "int64",
            "double": "double", "timestamp[us, tz=UTC]": "dateTime"}

# nazwa w modelu -> (tabela Delta, opis)
TABLES = {
    "Data": ("dim_data", "Kalendarz 03.08-28.10.2026. Dzień bieżący scenariusza to 28.10.2026."),
    "Magazyn": ("dim_magazyn", "Magazyny i centra dystrybucyjne (fikcyjne)."),
    "Miasto": ("dim_miasto", "Miasta z dostawą vanem i magazyn, który je obsługuje."),
    "Strefa": ("dim_strefa", "Strefy dostaw (dzielnice) w miastach."),
    "Okno": ("dim_okno", "Dwugodzinne okna dostaw 06:00-22:00."),
    "Produkt": ("dim_produkt", "Fikcyjny katalog produktów z kategorią i dostawcą."),
    "Dostawca": ("dim_dostawca", "Fikcyjni dostawcy."),
    "Przyczyna spóźnienia": ("dim_przyczyna_spoznienia", "Słownik przyczyn spóźnień dostaw."),
    "Przyczyna odpisu": ("dim_przyczyna_odpisu", "Słownik przyczyn odpisów."),
    "Zamówienia": ("fact_zamowienie", "Jedno zamówienie = jedna dostawa do klienta w wybranym oknie."),
    "Linie zamówień": ("fact_linia_zamowienia", "Pozycje zamówień ze statusem kompletacji: Kompletna, "
                       "Zamiennik, Częściowa, Brak."),
    "Kursy": ("fact_kurs", "Kursy vanów: planowany i faktyczny wyjazd z magazynu."),
    "Odpisy": ("fact_odpis", "Odpisy (straty) towaru w magazynach, wartość w cenie zakupu."),
    "Log ładowań": ("it_log_ladowan", "Log nocnych ładowań danych z systemów SKLEP, WMS, TMS, ERP. "
                    "data_biznesowa to dzień, którego dotyczą dane; ładowanie odbywa się następnej nocy."),
    "Kontrole jakości": ("it_kontrola_jakosci", "Wyniki automatycznych kontroli jakości danych po ładowaniu."),
}

RELATIONSHIPS = [
    ("Zamówienia", "data_dostawy", "Data", "data"),
    ("Zamówienia", "miasto_id", "Miasto", "miasto_id"),
    ("Zamówienia", "strefa_id", "Strefa", "strefa_id"),
    ("Zamówienia", "okno_id", "Okno", "okno_id"),
    ("Zamówienia", "przyczyna_spoznienia_kod", "Przyczyna spóźnienia", "przyczyna_spoznienia_kod"),
    ("Miasto", "magazyn_id", "Magazyn", "magazyn_id"),
    ("Linie zamówień", "zamowienie_id", "Zamówienia", "zamowienie_id"),
    ("Linie zamówień", "sku_id", "Produkt", "sku_id"),
    ("Produkt", "dostawca_id", "Dostawca", "dostawca_id"),
    ("Kursy", "data", "Data", "data"),
    ("Kursy", "miasto_id", "Miasto", "miasto_id"),
    ("Odpisy", "data", "Data", "data"),
    ("Odpisy", "magazyn_id", "Magazyn", "magazyn_id"),
    ("Odpisy", "sku_id", "Produkt", "sku_id"),
    ("Odpisy", "przyczyna_odpisu_kod", "Przyczyna odpisu", "przyczyna_odpisu_kod"),
    ("Log ładowań", "data_biznesowa", "Data", "data"),
    ("Kontrole jakości", "data_biznesowa", "Data", "data"),
]

SORT_BY = {("Data", "tydzien"): "poczatek_tygodnia", ("Data", "miesiac"): "miesiac_nr",
           ("Data", "dzien_tygodnia"): "dzien_tygodnia_nr", ("Okno", "okno"): "godzina_od"}

INT, PCT, PLN, DEC = "#,0", "0.0%", "#,0 zł", "#,0.0"
Z, L, O, K, LG, KJ = "'Zamówienia'", "'Linie zamówień'", "'Odpisy'", "'Kursy'", "'Log ładowań'", "'Kontrole jakości'"
MEASURES = [
    ("Zamówienia", "Liczba zamówień", f"COUNTROWS({Z})", INT, "Liczba zamówień (dostaw)."),
    ("Zamówienia", "Wartość zamówień", f"SUM({Z}[wartosc_zamowienia])", PLN, "Wartość zamówiona brutto."),
    ("Zamówienia", "Średni koszyk", "DIVIDE([Wartość zamówień], [Liczba zamówień])", "#,0.00 zł", None),
    ("Zamówienia", "Dostawy z danymi", f'CALCULATE(COUNTROWS({Z}), {Z}[status_dostawy] = "Dostarczono")', INT,
     "Dostawy z zarejestrowanym czasem doręczenia w TMS."),
    ("Zamówienia", "Dostawy w oknie", f"CALCULATE(COUNTROWS({Z}), {Z}[w_oknie] = TRUE())", INT, None),
    ("Zamówienia", "Dostawy spóźnione", f"CALCULATE(COUNTROWS({Z}), {Z}[w_oknie] = FALSE())", INT,
     "Dostawy doręczone po końcu okna."),
    ("Zamówienia", "Punktualność %", "DIVIDE([Dostawy w oknie], [Dostawy z danymi])", PCT,
     "Odsetek dostaw doręczonych w wybranym oknie, liczony tylko z dostaw z danymi z TMS."),
    ("Zamówienia", "Średnie spóźnienie (min)",
     f"CALCULATE(AVERAGE({Z}[minuty_spoznienia]), {Z}[w_oknie] = FALSE())", DEC,
     "Średnia minut po końcu okna dla dostaw spóźnionych."),
    ("Zamówienia", "Spóźnienia >30 min", f"CALCULATE(COUNTROWS({Z}), {Z}[minuty_spoznienia] > 30)", INT, None),
    ("Zamówienia", "Zamówienia bez danych TMS",
     f'CALCULATE(COUNTROWS({Z}), {Z}[status_dostawy] = "Brak danych z TMS")', INT,
     "Zamówienia bez zdarzenia doręczenia z TMS (luka w danych, nie w operacji)."),
    ("Zamówienia", "Zamówienia kompletne %",
     f"DIVIDE(CALCULATE(COUNTROWS({Z}), {Z}[czy_kompletne] = TRUE()), [Liczba zamówień])", PCT,
     "Odsetek zamówień, w których wszystkie linie wydano bez braków i zamienników."),
    ("Linie zamówień", "Linie zamówione", f"COUNTROWS({L})", INT, None),
    ("Linie zamówień", "Linie z brakiem", f'CALCULATE(COUNTROWS({L}), {L}[status_linii] = "Brak")', INT, None),
    ("Linie zamówień", "Udział braków %", "DIVIDE([Linie z brakiem], [Linie zamówione])", PCT,
     "Odsetek linii niewydanych w ogóle."),
    ("Linie zamówień", "Linie z zamiennikiem",
     f'CALCULATE(COUNTROWS({L}), {L}[status_linii] = "Zamiennik")', INT, None),
    ("Linie zamówień", "Udział zamienników %", "DIVIDE([Linie z zamiennikiem], [Linie zamówione])", PCT, None),
    ("Linie zamówień", "Zamienniki odrzucone %",
     f"DIVIDE(CALCULATE(COUNTROWS({L}), {L}[zamiennik_odrzucony] = TRUE()), [Linie z zamiennikiem])", PCT,
     "Odsetek zamienników odrzuconych przez klienta przy odbiorze."),
    ("Linie zamówień", "Linie niekompletne %",
     f'DIVIDE(CALCULATE(COUNTROWS({L}), {L}[status_linii] <> "Kompletna"), [Linie zamówione])', PCT,
     "Braki, zamienniki i wydania częściowe razem."),
    ("Linie zamówień", "Wartość utracona", f"SUM({L}[wartosc_utracona])", PLN,
     "Wartość niewydanego towaru (braki, częściowe, odrzucone zamienniki)."),
    ("Linie zamówień", "Sprzedaż wartość", f"SUM({L}[wartosc_wydana])", PLN, "Wartość towaru wydanego klientom."),
    ("Odpisy", "Odpisy wartość", f"SUM({O}[wartosc_kosztowa])", PLN, "Wartość odpisów w cenie zakupu."),
    ("Odpisy", "Odpisy sztuki", f"SUM({O}[ilosc])", INT, None),
    ("Odpisy", "Odpisy % sprzedaży", "DIVIDE([Odpisy wartość], [Sprzedaż wartość])", "0.00%",
     "Wartość odpisów do wartości sprzedaży w tym samym zakresie."),
    ("Kursy", "Liczba kursów", f"COUNTROWS({K})", INT, None),
    ("Kursy", "Opóźnione wyjazdy", f"CALCULATE(COUNTROWS({K}), {K}[opoznienie_wyjazdu_min] > 15)", INT,
     "Kursy, które wyjechały z magazynu ponad 15 minut po planie."),
    ("Kursy", "Średnie opóźnienie wyjazdu (min)", f"AVERAGE({K}[opoznienie_wyjazdu_min])", DEC, None),
    ("Log ładowań", "Ładowania", f"COUNTROWS({LG})", INT, None),
    ("Log ładowań", "Ładowania niepełne", f'CALCULATE(COUNTROWS({LG}), {LG}[status] <> "Sukces")', INT,
     "Ładowania ze statusem Błąd lub Częściowy."),
    ("Log ładowań", "Kompletność ładowań %",
     f"DIVIDE(SUM({LG}[wiersze_zaladowane]), SUM({LG}[wiersze_oczekiwane]))", "0.00%", None),
    ("Log ładowań", "Ostatnie ładowanie", f"MAX({LG}[koniec_ladowania])", "dd.mm.yyyy hh:nn", None),
    ("Kontrole jakości", "Kontrole niezaliczone",
     f'CALCULATE(COUNTROWS({KJ}), {KJ}[wynik] = "Niezaliczona")', INT, None),
    ("Kontrole jakości", "Kontrole z ostrzeżeniem",
     f'CALCULATE(COUNTROWS({KJ}), {KJ}[wynik] = "Ostrzeżenie")', INT, None),
]


def tag() -> str:
    return str(uuid.uuid4())


def build_model(ws: str, lh: str) -> dict:
    tables = []
    for name, (delta, desc) in TABLES.items():
        cols = []
        for f in SCHEMAS[delta]:
            dt = TYPE_MAP[f["type"]]
            c = {"name": f["name"], "dataType": dt, "sourceColumn": f["name"], "lineageTag": tag(),
                 "summarizeBy": "none"}
            if f["type"].startswith("date32"):
                c["formatString"] = "dd.mm.yyyy"
            elif dt == "dateTime":
                c["formatString"] = "dd.mm.yyyy hh:nn"
            if (name, f["name"]) in SORT_BY:
                c["sortByColumn"] = SORT_BY[(name, f["name"])]
            if name == "Data" and f["name"] == "data":
                c["isKey"] = True
            cols.append(c)
        t = {"name": name, "description": desc, "lineageTag": tag(), "columns": cols,
             "partitions": [{"name": name, "mode": "directLake",
                             "source": {"type": "entity", "entityName": delta, "expressionSource": "DatabaseQuery"}}]}
        if name == "Data":
            t["dataCategory"] = "Time"
        ms = [{"name": n, "expression": e, "formatString": f, "lineageTag": tag(), **({"description": d} if d else {})}
              for tb, n, e, f, d in MEASURES if tb == name]
        if ms:
            t["measures"] = ms
        tables.append(t)
    rels = []
    for i, (ft, fc, tt, tc) in enumerate(RELATIONSHIPS, 1):
        for tn, cn in ((ft, fc), (tt, tc)):
            assert any(c["name"] == cn for c in next(x for x in tables if x["name"] == tn)["columns"]), (tn, cn)
        rels.append({"name": f"rel_{i:02d}", "fromTable": ft, "fromColumn": fc, "toTable": tt, "toColumn": tc})
    return {
        "name": MODEL, "compatibilityLevel": 1604,
        "model": {
            "culture": "pl-PL", "collation": "Latin1_General_100_BIN2_UTF8",
            "dataAccessOptions": {"legacyRedirects": True, "returnErrorValuesAsNull": True},
            "defaultPowerBIDataSourceVersion": "powerBI_V3", "sourceQueryCulture": "pl-PL",
            "expressions": [{"name": "DatabaseQuery", "kind": "m", "lineageTag": tag(),
                             "expression": "let\n    Source = AzureStorage.DataLake("
                                           f'"https://onelake.dfs.fabric.microsoft.com/{ws}/{lh}")\nin\n    Source'}],
            "tables": tables, "relationships": rels,
        },
    }


def dax(model_id: str, query: str) -> list[dict]:
    r = requests.post(f"{PBI}/datasets/{model_id}/executeQueries", headers=h(PBI_RES),
                      json={"queries": [{"query": query}], "serializerSettings": {"includeNulls": True}})
    if r.status_code != 200:
        raise RuntimeError(r.text)
    return r.json()["results"][0]["tables"][0]["rows"]


def main() -> None:
    s = load_state()
    ws, lh = s["workspace_id"], s["lakehouse_id"]
    model = build_model(ws, lh)
    (ROOT / ".fabric" / "model.bim").write_text(json.dumps(model, indent=2, ensure_ascii=False), encoding="utf-8")
    mid = upsert_item(ws, MODEL, "SemanticModel",
                      [part("model.bim", model), part("definition.pbism", {"version": "1.0", "settings": {}})])
    s["semantic_model_id"] = mid
    save_state(s)
    print("model", mid)
    r = requests.post(f"{PBI}/groups/{ws}/datasets/{mid}/refreshes", headers=h(PBI_RES), json={"type": "full"})
    print("refresh", r.status_code)
    time.sleep(20)

    ctrl = json.loads((ROOT / "data" / "_kontrolne.json").read_text(encoding="utf-8"))
    row = dax(mid, 'EVALUATE ROW("zam", [Liczba zamówień], "lin", [Linie zamówione], "pkt", [Punktualność %], '
                   '"brak", [Udział braków %], "odp", [Odpisy wartość], "it", [Ładowania niepełne])')[0]
    print(json.dumps(row, ensure_ascii=False))
    got = list(row.values())
    exp = [ctrl["zamowienia"], ctrl["linie"], ctrl["punktualnosc_pct"] / 100, ctrl["braki_pct"] / 100,
           ctrl["odpisy_wartosc"], ctrl["it_ladowania_niepelne"]]
    for g, e in zip(got, exp):
        assert abs(float(g) - e) <= max(1e-4, abs(e) * 1e-4), (g, e)
    print("kontrola zgodna z _kontrolne.json")
    for q in ['EVALUATE TOPN(3, SUMMARIZECOLUMNS(Miasto[miasto], "p", [Punktualność %]), [p], ASC)',
              'EVALUATE TOPN(3, SUMMARIZECOLUMNS(Dostawca[dostawca], Data[miesiac], "b", [Udział braków %]), [b], DESC)',
              'EVALUATE CALCULATETABLE(SUMMARIZECOLUMNS(\'Log ładowań\'[tabela], \'Log ładowań\'[status], '
              '"w", SUM(\'Log ładowań\'[wiersze_zaladowane])), \'Log ładowań\'[status] <> "Sukces")']:
        print(json.dumps(dax(mid, q), ensure_ascii=False))


if __name__ == "__main__":
    main()
