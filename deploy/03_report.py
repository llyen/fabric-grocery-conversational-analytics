"""Raport PBIR rpt_northwind_operacje (4 strony) nad sm_northwind_operacje."""
from __future__ import annotations

import importlib.util
import json

from common import REPORT, ROOT, get_definition, load_state, part, save_state, upsert_item

W, H = 1280, 720
SCHEMA_VIS = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.0.0/schema.json"
SCHEMA_PAGE = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/1.4.0/schema.json"
SCHEMA_PAGES = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/pagesMetadata/1.0.0/schema.json"
SCHEMA_REPORT = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/report/1.3.0/schema.json"
SCHEMA_PBIR = "https://developer.microsoft.com/json-schemas/fabric/item/report/definitionProperties/1.0.0/schema.json"
SCHEMA_VERSION = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/versionMetadata/1.0.0/schema.json"
FOOTER = "Dane syntetyczne przygotowane na potrzeby demo. Nie są to dane żadnej rzeczywistej firmy."
THEME_FILE = "Northwind-Light.json"

_spec = importlib.util.spec_from_file_location("sm", ROOT / "deploy" / "02_semantic_model.py")
SM = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(SM)


def col(e: str, p: str) -> dict:
    return {"field": {"Column": {"Expression": {"SourceRef": {"Entity": e}}, "Property": p}},
            "queryRef": f"{e}.{p}", "nativeQueryRef": p}


def mea(e: str, p: str) -> dict:
    return {"field": {"Measure": {"Expression": {"SourceRef": {"Entity": e}}, "Property": p}},
            "queryRef": f"{e}.{p}", "nativeQueryRef": p}


def lit(v: str) -> dict:
    return {"expr": {"Literal": {"Value": f"'{v}'"}}}


def visual(name, vtype, x, y, w, h, roles=None, title=None, objects=None, filters=None) -> dict:
    v: dict = {"visualType": vtype}
    if roles:
        v["query"] = {"queryState": {r: {"projections": p} for r, p in roles.items()}}
    if objects:
        v["objects"] = objects
    if title:
        v["visualContainerObjects"] = {"title": [{"properties": {
            "show": {"expr": {"Literal": {"Value": "true"}}}, "text": lit(title)}}]}
    out = {"$schema": SCHEMA_VIS, "name": name,
           "position": {"x": x, "y": y, "z": 0, "width": w, "height": h, "tabOrder": 0}, "visual": v}
    if filters:
        out["filterConfig"] = {"filters": filters}
    return out


def textbox(name, x, y, w, h, text, size="11pt", color="#3C3C3C", bold=False) -> dict:
    style = {"fontFamily": "Segoe UI", "fontSize": size, "color": color}
    if bold:
        style["fontWeight"] = "bold"
    return visual(name, "textbox", x, y, w, h, objects={"general": [{"properties": {"paragraphs": [
        {"textRuns": [{"value": text, "textStyle": style}]}]}}]})


def header(n: int, title: str, question: str) -> list[dict]:
    return [textbox(f"p{n}_hdr", 16, 6, 1000, 38, title, "20pt", "#312E81", True),
            textbox(f"p{n}_sub", 16, 42, 1000, 28, question, "11pt", "#5A5A5A"),
            textbox(f"p{n}_ftr", 16, H - 26, 1000, 22, FOOTER, "9pt", "#8C8C8C")]


def cards(n: int, items: list[tuple[str, str, str]]) -> list[dict]:
    w = (W - 32 - 12 * (len(items) - 1)) // len(items)
    return [visual(f"p{n}_c{i + 1}", "card", 16 + i * (w + 12), 76, w, 92, {"Values": [mea(e, m)]}, title=t)
            for i, (e, m, t) in enumerate(items)]


def not_in_filter(entity: str, prop: str, value: str) -> dict:
    return {"name": "fltNotSuccess", "type": "Categorical",
            "field": {"Column": {"Expression": {"SourceRef": {"Entity": entity}}, "Property": prop}},
            "filter": {"Version": 2, "From": [{"Name": "t", "Entity": entity, "Type": 0}],
                       "Where": [{"Condition": {"Not": {"Expression": {"In": {
                           "Expressions": [{"Column": {"Expression": {"SourceRef": {"Source": "t"}}, "Property": prop}}],
                           "Values": [[{"Literal": {"Value": f"'{value}'"}}]]}}}}}]}}


Z, L, O, K = "Zamówienia", "Linie zamówień", "Odpisy", "Kursy"
LG, KJ = "Log ładowań", "Kontrole jakości"


def page1():
    v = header(1, "Punktualność dostaw", "Gdzie i w których oknach spóźniamy się najczęściej i dlaczego?")
    v += cards(1, [(Z, "Punktualność %", "Punktualność"), (Z, "Dostawy spóźnione", "Dostawy spóźnione"),
                   (Z, "Średnie spóźnienie (min)", "Średnie spóźnienie (min)"),
                   (Z, "Spóźnienia >30 min", "Spóźnienia ponad 30 min"),
                   (K, "Opóźnione wyjazdy", "Wyjazdy z magazynu opóźnione >15 min")])
    v.append(visual("p1_trend", "lineChart", 16, 180, 620, 250,
                    {"Category": [col("Data", "tydzien")], "Y": [mea(Z, "Punktualność %")]},
                    "Punktualność wg tygodnia"))
    v.append(visual("p1_city", "barChart", 648, 180, 400, 250,
                    {"Category": [col("Miasto", "miasto")], "Y": [mea(Z, "Punktualność %")]},
                    "Punktualność wg miasta"))
    v.append(visual("p1_sl_m", "slicer", 1060, 180, 204, 120, {"Values": [col("Data", "miesiac")]}, "Miesiąc"))
    v.append(visual("p1_sl_c", "slicer", 1060, 310, 204, 120, {"Values": [col("Miasto", "miasto")]}, "Miasto"))
    v.append(visual("p1_mx", "pivotTable", 16, 440, 820, 250,
                    {"Rows": [col("Okno", "okno")], "Columns": [col("Miasto", "miasto")],
                     "Values": [mea(Z, "Punktualność %")]}, "Punktualność: okno dostawy x miasto"))
    v.append(visual("p1_why", "barChart", 848, 440, 416, 250,
                    {"Category": [col("Przyczyna spóźnienia", "przyczyna_spoznienia")],
                     "Y": [mea(Z, "Dostawy spóźnione")]}, "Przyczyny spóźnień"))
    return "p1Punktualnosc", "Punktualność", v


def page2():
    v = header(2, "Braki i zamienniki", "Których produktów i dostawców brakuje i ile nas to kosztuje?")
    v += cards(2, [(L, "Linie niekompletne %", "Linie niekompletne"), (L, "Udział braków %", "Braki"),
                   (L, "Udział zamienników %", "Zamienniki"), (L, "Zamienniki odrzucone %", "Zamienniki odrzucone"),
                   (L, "Wartość utracona", "Wartość utracona")])
    v.append(visual("p2_trend", "columnChart", 16, 180, 620, 250,
                    {"Category": [col("Data", "tydzien")], "Y": [mea(L, "Linie niekompletne %")]},
                    "Linie niekompletne wg tygodnia"))
    v.append(visual("p2_cat", "barChart", 648, 180, 400, 250,
                    {"Category": [col("Produkt", "kategoria")], "Y": [mea(L, "Linie niekompletne %")]},
                    "Linie niekompletne wg kategorii"))
    v.append(visual("p2_sl_m", "slicer", 1060, 180, 204, 120, {"Values": [col("Data", "miesiac")]}, "Miesiąc"))
    v.append(visual("p2_sl_w", "slicer", 1060, 310, 204, 120, {"Values": [col("Magazyn", "magazyn")]}, "Magazyn"))
    v.append(visual("p2_sup", "barChart", 16, 440, 620, 250,
                    {"Category": [col("Dostawca", "dostawca")], "Y": [mea(L, "Udział braków %")]},
                    "Udział braków wg dostawcy"))
    v.append(visual("p2_lost", "barChart", 648, 440, 616, 250,
                    {"Category": [col("Magazyn", "magazyn")], "Y": [mea(L, "Wartość utracona")]},
                    "Wartość utracona wg magazynu"))
    return "p2Braki", "Braki i zamienniki", v


def page3():
    v = header(3, "Straty świeżych", "Co odpisujemy, gdzie i z jakiego powodu?")
    v += cards(3, [(O, "Odpisy wartość", "Odpisy (cena zakupu)"), (O, "Odpisy sztuki", "Odpisy (szt.)"),
                   (O, "Odpisy % sprzedaży", "Odpisy jako % sprzedaży")])
    v.append(visual("p3_trend", "columnChart", 16, 180, 620, 250,
                    {"Category": [col("Data", "tydzien")], "Y": [mea(O, "Odpisy wartość")]},
                    "Odpisy wg tygodnia"))
    v.append(visual("p3_why", "donutChart", 648, 180, 400, 250,
                    {"Category": [col("Przyczyna odpisu", "przyczyna_odpisu")], "Y": [mea(O, "Odpisy wartość")]},
                    "Odpisy wg przyczyny"))
    v.append(visual("p3_sl_m", "slicer", 1060, 180, 204, 120, {"Values": [col("Data", "miesiac")]}, "Miesiąc"))
    v.append(visual("p3_sl_t", "slicer", 1060, 310, 204, 120,
                    {"Values": [col("Produkt", "strefa_temperaturowa")]}, "Strefa temperaturowa"))
    v.append(visual("p3_podkat", "barChart", 16, 440, 620, 250,
                    {"Category": [col("Produkt", "podkategoria")], "Y": [mea(O, "Odpisy % sprzedaży")]},
                    "Odpisy jako % sprzedaży wg podkategorii"))
    v.append(visual("p3_wh", "barChart", 648, 440, 616, 250,
                    {"Category": [col("Magazyn", "magazyn")], "Y": [mea(O, "Odpisy wartość")]},
                    "Odpisy wg magazynu"))
    return "p3Straty", "Straty świeżych", v


def page4():
    v = header(4, "Świeżość i jakość danych (IT)", "Czy dane, na których pracuje biznes i agent, są kompletne?")
    v += cards(4, [(LG, "Ostatnie ładowanie", "Ostatnie ładowanie"), (LG, "Ładowania niepełne", "Ładowania niepełne"),
                   (LG, "Kompletność ładowań %", "Kompletność wierszy"),
                   (KJ, "Kontrole niezaliczone", "Kontrole niezaliczone"),
                   (Z, "Zamówienia bez danych TMS", "Zamówienia bez danych z TMS")])
    v.append(visual("p4_bad", "tableEx", 16, 180, 1248, 200,
                    {"Values": [col(LG, "data_biznesowa"), col(LG, "system_zrodlowy"), col(LG, "tabela"),
                                col(LG, "status"), col(LG, "proba"), col(LG, "wiersze_zaladowane"),
                                col(LG, "wiersze_oczekiwane"), col(LG, "komunikat_bledu")]},
                    "Ładowania zakończone inaczej niż Sukces", filters=[not_in_filter(LG, "status", "Sukces")]))
    v.append(visual("p4_dq", "pivotTable", 16, 390, 620, 300,
                    {"Rows": [col(KJ, "kontrola")], "Columns": [col(KJ, "wynik")],
                     "Values": [mea(KJ, "Kontrole niezaliczone"), mea(KJ, "Kontrole z ostrzeżeniem")]},
                    "Kontrole jakości danych"))
    v.append(visual("p4_sys", "columnChart", 648, 390, 400, 300,
                    {"Category": [col(LG, "system_zrodlowy")], "Y": [mea(LG, "Kompletność ładowań %")]},
                    "Kompletność wierszy wg systemu"))
    v.append(visual("p4_sl_w", "slicer", 1060, 390, 204, 300, {"Values": [col("Data", "tydzien")]}, "Tydzień"))
    return "p4DaneIT", "Świeżość danych (IT)", v


THEME = {
    "name": "Northwind-Light",
    "dataColors": ["#4F46E5", "#F28C28", "#4A90D9", "#C0392B", "#8E6BBF", "#0EA5E9", "#D4AC0D", "#7F8C8D"],
    "background": "#FFFFFF", "foreground": "#252525", "tableAccent": "#4F46E5",
    "visualStyles": {
        "*": {"*": {"background": [{"color": {"solid": {"color": "#FFFFFF"}}, "transparency": 0}],
                    "border": [{"show": True, "color": {"solid": {"color": "#E4E4F0"}}, "radius": 6}],
                    "title": [{"show": True, "fontColor": {"solid": {"color": "#312E81"}}, "fontSize": 11}]}},
        "page": {"*": {"background": [{"color": {"solid": {"color": "#F5F5FA"}}, "transparency": 0}]}},
        "card": {"*": {"labels": [{"color": {"solid": {"color": "#4F46E5"}}, "fontSize": 24}],
                       "categoryLabels": [{"show": False}]}},
        "textbox": {"*": {"background": [{"show": False}], "border": [{"show": False}]}},
    },
}


def build_parts(model_id: str) -> list[dict]:
    parts = [
        part("definition.pbir", {"$schema": SCHEMA_PBIR, "version": "4.0", "datasetReference": {"byConnection": {
            "connectionString": None, "pbiServiceModelId": None, "pbiModelVirtualServerName": "sobe_wowvirtualserver",
            "pbiModelDatabaseName": model_id, "connectionType": "pbiServiceXmlaStyleLive",
            "name": "EntityDataSource"}}}),
        part("definition/version.json", {"$schema": SCHEMA_VERSION, "version": "2.0.0"}),
        part("definition/report.json", {
            "$schema": SCHEMA_REPORT,
            "themeCollection": {"baseTheme": {"name": "CY24SU02", "reportVersionAtImport": "5.55",
                                              "type": "SharedResources"},
                                "customTheme": {"name": THEME_FILE, "reportVersionAtImport": "5.55",
                                                "type": "RegisteredResources"}},
            "resourcePackages": [{"name": "RegisteredResources", "type": "RegisteredResources",
                                  "items": [{"name": THEME_FILE, "path": THEME_FILE, "type": "CustomTheme"}]}],
            "layoutOptimization": "None",
            "settings": {"useStylableVisualContainerHeader": True, "defaultDrillFilterOtherVisuals": True}}),
        part(f"StaticResources/RegisteredResources/{THEME_FILE}", THEME),
    ]
    order = []
    for build in (page1, page2, page3, page4):
        name, display, visuals = build()
        order.append(name)
        parts.append(part(f"definition/pages/{name}/page.json", {
            "$schema": SCHEMA_PAGE, "name": name, "displayName": display, "displayOption": "FitToPage",
            "height": H, "width": W}))
        for v in visuals:
            parts.append(part(f"definition/pages/{name}/visuals/{v['name']}/visual.json", v))
    parts.append(part("definition/pages/pages.json",
                      {"$schema": SCHEMA_PAGES, "pageOrder": order, "activePageName": order[0]}))
    return parts


def validate() -> None:
    cols = {t: {f["name"] for f in SM.SCHEMAS[d]} for t, (d, _) in SM.TABLES.items()}
    meas = {n: t for t, n, *_ in SM.MEASURES}
    errors, n = [], 0
    for build in (page1, page2, page3, page4):
        pname, _, visuals = build()
        seen = set()
        for v in visuals:
            nm, pos = v["name"], v["position"]
            assert nm not in seen and len(nm) <= 50 and all(c.isalnum() or c in "-_" for c in nm), nm
            seen.add(nm)
            if pos["x"] + pos["width"] > W or pos["y"] + pos["height"] > H:
                errors.append(f"{pname}/{nm} poza kanwą")
            for role, blk in v["visual"].get("query", {}).get("queryState", {}).items():
                for pr in blk["projections"]:
                    f, n = pr["field"], n + 1
                    if "Measure" in f:
                        e, p = f["Measure"]["Expression"]["SourceRef"]["Entity"], f["Measure"]["Property"]
                        if meas.get(p) != e:
                            errors.append(f"{pname}/{nm}: miara {e}[{p}]")
                    else:
                        e, p = f["Column"]["Expression"]["SourceRef"]["Entity"], f["Column"]["Property"]
                        if p not in cols.get(e, set()):
                            errors.append(f"{pname}/{nm}: kolumna {e}[{p}]")
    if errors:
        raise SystemExit("\n".join(errors))
    print(f"walidacja OK, {n} odwołań do modelu")


def main() -> None:
    validate()
    s = load_state()
    ws = s["workspace_id"]
    rid = upsert_item(ws, REPORT, "Report", build_parts(s["semantic_model_id"]))
    s["report_id"] = rid
    save_state(s)
    back = get_definition(ws, rid)
    pages = [p for p in back if p.endswith("page.json")]
    vis = [p for p in back if p.endswith("visual.json")]
    print(f"raport {rid}: {len(pages)} stron, {len(vis)} wizualizacji po odczycie")
    print(f"https://app.fabric.microsoft.com/groups/{ws}/reports/{rid}")


if __name__ == "__main__":
    main()
