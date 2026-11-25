"""Buduje src/data/snapshot.json dla aplikacji Northwind Operacje z tych samych parquetów, które trafiły do lakehouse.

Uruchom z katalogu app:  python scripts/build_snapshot.py
"""
from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
OUT = Path(__file__).resolve().parents[1] / "src" / "data" / "snapshot.json"

DZIS = date(2026, 10, 28)
WCZORAJ = DZIS - timedelta(days=1)
TYDZ_OD, TYDZ_DO = date(2026, 10, 19), date(2026, 10, 25)


def rd(name: str, **kw) -> pd.DataFrame:
    return pd.read_parquet(DATA / f"{name}.parquet", **kw)


def pc(x: float, n: int = 1) -> str:
    return f"{x:.{n}f}%".replace(".", ",")


def zl(x: float) -> str:
    return f"{x:,.0f} zł".replace(",", " ")


def main() -> None:
    miasto = rd("dim_miasto")
    magazyn = rd("dim_magazyn")
    okno = rd("dim_okno")
    dostawca = rd("dim_dostawca")
    produkt = rd("dim_produkt")
    p_sp = rd("dim_przyczyna_spoznienia")
    p_od = rd("dim_przyczyna_odpisu")
    mname = dict(zip(miasto.miasto_id, miasto.miasto))
    rname = dict(zip(p_sp.przyczyna_spoznienia_kod, p_sp.przyczyna_spoznienia))
    dname = dict(zip(dostawca.dostawca_id, dostawca.dostawca))

    zam = rd("fact_zamowienie", columns=["zamowienie_id", "data_dostawy", "miasto_id", "okno_id", "w_oknie",
                                         "przyczyna_spoznienia_kod", "status_dostawy"])
    zam["d"] = pd.to_datetime(zam.data_dostawy).dt.date
    zam["w_oknie"] = zam.w_oknie.astype("boolean")
    zam["bez_tms"] = zam.status_dostawy == "Brak danych z TMS"

    lin = rd("fact_linia_zamowienia", columns=["zamowienie_id", "sku_id", "status_linii",
                                                "wartosc_zamowiona", "wartosc_wydana", "wartosc_utracona"])
    lin = lin.merge(zam[["zamowienie_id", "d", "miasto_id"]], on="zamowienie_id")
    lin["niekompletna"] = lin.status_linii != "Kompletna"
    lin["brak"] = lin.status_linii == "Brak"

    odp = rd("fact_odpis")
    odp["d"] = pd.to_datetime(odp.data).dt.date
    kurs = rd("fact_kurs", columns=["data", "miasto_id", "opoznienie_wyjazdu_min"])
    kurs["d"] = pd.to_datetime(kurs.data).dt.date

    # ---------------------------------------------------------------- dzienne KPI per miasto
    z_ok = zam[zam.w_oknie.notna()].copy()
    z_ok["w"] = z_ok.w_oknie.astype(bool)
    g = zam.groupby(["d", "miasto_id"])
    dz = pd.DataFrame({"zam": g.size(), "bez_tms": g.bez_tms.sum()})
    gz = z_ok.groupby(["d", "miasto_id"])
    dz["pomiar"] = gz.size()
    dz["punkt"] = gz.w.sum()
    gl = lin.groupby(["d", "miasto_id"])
    dz["linie"] = gl.size()
    dz["linie_nk"] = gl.niekompletna.sum()
    dz["linie_brak"] = gl.brak.sum()
    dz["wart_zam"] = gl.wartosc_zamowiona.sum()
    dz["wart_wyd"] = gl.wartosc_wydana.sum()
    dz["wart_utr"] = gl.wartosc_utracona.sum()
    dz["wyj_opozn"] = kurs[kurs.opoznienie_wyjazdu_min > 15].groupby(["d", "miasto_id"]).size()
    dz = dz.fillna(0).reset_index()
    dzienne = [
        {"d": r.d.isoformat(), "m": r.miasto_id, "zam": int(r.zam), "pomiar": int(r.pomiar), "punkt": int(r.punkt),
         "bezTms": int(r.bez_tms), "linie": int(r.linie), "linieNk": int(r.linie_nk), "linieBrak": int(r.linie_brak),
         "wartZam": round(float(r.wart_zam), 2), "wartWyd": round(float(r.wart_wyd), 2),
         "wartUtr": round(float(r.wart_utr), 2), "wyjOpozn": int(r.wyj_opozn)}
        for r in dz.itertuples()
    ]

    od_g = odp.groupby(["d", "magazyn_id"]).wartosc_kosztowa.sum().reset_index()
    odpisy = [{"d": r.d.isoformat(), "mag": r.magazyn_id, "wart": round(float(r.wartosc_kosztowa), 2)}
              for r in od_g.itertuples()]

    o7 = z_ok[(z_ok.d >= WCZORAJ - timedelta(days=6)) & ~z_ok.w]
    przyczyny7 = [{"m": m, "kod": k, "n": int(n)}
                  for (m, k), n in o7.groupby(["miasto_id", "przyczyna_spoznienia_kod"]).size().items()]

    # ---------------------------------------------------------------- sygnały (wyliczone z danych)
    sygnaly = []

    tw = z_ok[(z_ok.d >= TYDZ_OD) & (z_ok.d <= TYDZ_DO)]
    city_w = tw.groupby("miasto_id").w.mean().sort_values()
    worst = city_w.index[0]
    wk = z_ok[z_ok.miasto_id == worst].merge(okno, on="okno_id")
    win = (1 - wk.groupby("okno").w.mean()).sort_values(ascending=False)
    w_name = win.index[0]
    w_reason = wk[(wk.okno == w_name) & ~wk.w].przyczyna_spoznienia_kod.value_counts(normalize=True)
    sygnaly.append({
        "id": "rze-punktualnosc", "obszar": "Dostawy", "odbiorca": "COO", "waga": "wysoka", "miasto": worst,
        "tytul": f"{mname[worst]} z najniższą punktualnością w zeszłym tygodniu",
        "liczba": pc(100 * city_w.iloc[0]),
        "opis": (f"W tygodniu {TYDZ_OD:%d.%m}-{TYDZ_DO:%d.%m} punktualność w mieście {mname[worst]} wyniosła "
                 f"{pc(100 * city_w.iloc[0])} przy średniej sieci {pc(100 * tw.w.mean())}. "
                 f"W całym okresie od sierpnia najgorsze okno to {w_name} z {pc(100 * win.iloc[0])} spóźnień. "
                 f"{pc(100 * w_reason.iloc[0], 0)} z nich to {rname[w_reason.index[0]].lower()}."),
        "pytanie": "W których oknach Rzeszów spóźnia się najczęściej i z jakiego powodu?",
        "strona": "p1Punktualnosc",
    })

    z_rain = z_ok[(z_ok.d >= date(2026, 10, 12)) & (z_ok.d <= date(2026, 10, 18))]
    z_base = z_ok[(z_ok.d >= date(2026, 9, 7)) & (z_ok.d <= date(2026, 10, 11))]
    rain_pog = (z_rain[~z_rain.w].przyczyna_spoznienia_kod == "POGODA").mean()
    sygnaly.append({
        "id": "pogoda-tydzien42", "obszar": "Dostawy", "odbiorca": "COO", "waga": "średnia", "miasto": None,
        "tytul": "Deszczowy tydzień 12-18.10 podniósł odsetek spóźnień w całej sieci",
        "liczba": pc(100 * (1 - z_rain.w.mean())),
        "opis": (f"Spóźnienia w tygodniu 12-18.10 to {pc(100 * (1 - z_rain.w.mean()))} wobec "
                 f"{pc(100 * (1 - z_base.w.mean()))} w pięciu wcześniejszych tygodniach. "
                 f"Pogoda odpowiada za {pc(100 * rain_pog, 0)} spóźnień w tym tygodniu."),
        "pytanie": "Jak zmieniała się punktualność tydzień do tygodnia w październiku i co ją obniżyło w tygodniu 12-18.10?",
        "strona": "p1Punktualnosc",
    })

    mar = z_ok[z_ok.miasto_id.isin(["LUB", "ZAM"])].merge(okno, on="okno_id")
    mar_r = mar[mar.godzina_od <= 8]
    zator = mar_r[(mar_r.d >= date(2026, 9, 28)) & (mar_r.d <= date(2026, 10, 2))]
    przed = mar_r[(mar_r.d >= date(2026, 9, 14)) & (mar_r.d <= date(2026, 9, 25))]
    z_wyj = (zator[~zator.w].przyczyna_spoznienia_kod == "WYJAZD").mean()
    sygnaly.append({
        "id": "lublin-poranki", "obszar": "Dostawy", "odbiorca": "COO", "waga": "średnia", "miasto": "LUB",
        "tytul": "Zator kompletacji w centrum Lublin opóźnił poranne kursy 28.09-02.10",
        "liczba": pc(100 * zator.w.mean()),
        "opis": (f"Punktualność porannych okien (do 10:00) w Lublinie i Zamościu spadła do {pc(100 * zator.w.mean())} "
                 f"z {pc(100 * przed.w.mean())} w dwóch wcześniejszych tygodniach. "
                 f"{pc(100 * z_wyj, 0)} spóźnień ma przyczynę: opóźniony wyjazd z magazynu."),
        "pytanie": "Dlaczego pod koniec września spadła punktualność porannych dostaw z centrum Lublin?",
        "strona": "p1Punktualnosc",
    })

    paz = lin[lin.d >= date(2026, 10, 1)].merge(produkt[["sku_id", "dostawca_id"]], on="sku_id")
    sup = paz.groupby("dostawca_id").agg(utr=("wartosc_utracona", "sum"), br=("brak", "mean"),
                                         nk=("niekompletna", "mean"))
    sup["braki"] = 100 * sup.br
    sup = sup.sort_values("braki", ascending=False)
    top = sup.index[0]
    siec = 100 * paz.brak.mean()
    sygnaly.append({
        "id": "dostawca-braki", "obszar": "Braki", "odbiorca": "COO", "waga": "wysoka", "miasto": None,
        "tytul": f"{dname[top]} z najwyższym udziałem braków w październiku",
        "liczba": pc(sup.braki.iloc[0], 2),
        "opis": (f"Udział linii z brakiem u dostawcy {dname[top]} wynosi "
                 f"{pc(sup.braki.iloc[0], 2)} wobec {pc(siec, 2)} w całej sieci. "
                 f"Niekompletnych linii {pc(100 * sup.nk.iloc[0])}, utracona sprzedaż w październiku "
                 f"{zl(sup.utr.iloc[0])}."),
        "pytanie": "Którzy dostawcy mieli najwyższy udział braków w październiku?",
        "strona": "p2Braki",
    })

    rze7 = odp[(odp.d == date(2026, 10, 7)) & (odp.magazyn_id == "RZE")].merge(
        produkt[["sku_id", "kategoria"]], on="sku_id")
    t = rze7[rze7.przyczyna_odpisu_kod == "TEMPERATURA"]
    tk = t.groupby("kategoria").wartosc_kosztowa.sum().sort_values(ascending=False)
    avg_rze = odp[(odp.magazyn_id == "RZE") & (odp.d != date(2026, 10, 7))].groupby("d").wartosc_kosztowa.sum().mean()
    sygnaly.append({
        "id": "rze-odpisy-0710", "obszar": "Straty", "odbiorca": "COO", "waga": "wysoka", "miasto": "RZE",
        "tytul": "Jednodniowy skok odpisów w magazynie Rzeszów 7.10",
        "liczba": zl(rze7.wartosc_kosztowa.sum()),
        "opis": (f"Odpisy 7.10 w Rzeszowie wyniosły {zl(rze7.wartosc_kosztowa.sum())} przy średniej dziennej "
                 f"{zl(avg_rze)}. Przerwanie łańcucha chłodniczego to {zl(t.wartosc_kosztowa.sum())}, "
                 f"z czego największa pozycja to kategoria {tk.index[0]}: {zl(tk.iloc[0])}."),
        "pytanie": "Ile odpisaliśmy w magazynie w Rzeszowie 7 października i dlaczego?",
        "strona": "p3Straty",
    })

    log = rd("it_log_ladowan")
    log["data_biznesowa"] = pd.to_datetime(log.data_biznesowa).dt.date
    tms = log[(log.data_biznesowa == WCZORAJ) & (log.tabela == "tms_zdarzenia_dostaw")].iloc[0]
    bez = int(zam[zam.d == WCZORAJ].bez_tms.sum())
    miasta_bez = ", ".join(sorted(mname[m] for m in zam[(zam.d == WCZORAJ) & zam.bez_tms].miasto_id.unique()))
    sygnaly.append({
        "id": "tms-2710", "obszar": "Dane", "odbiorca": "IT", "waga": "wysoka", "miasto": None,
        "tytul": "Niepełne ładowanie zdarzeń dostaw z TMS za 27.10",
        "liczba": f"{int(tms.wiersze_zaladowane)} z {int(tms.wiersze_oczekiwane)}",
        "opis": (f"tms_zdarzenia_dostaw ma status {tms.status}: {int(tms.wiersze_zaladowane)} z "
                 f"{int(tms.wiersze_oczekiwane)} wierszy. {tms.komunikat_bledu} "
                 f"{bez} zamówień z 27.10 ({miasta_bez}) nie ma czasu doręczenia, "
                 f"więc punktualność za wczoraj jest liczona bez nich."),
        "pytanie": "Czy dane za wczoraj są kompletne?",
        "strona": "p4DaneIT",
    })

    wms = log[(log.data_biznesowa == date(2026, 10, 13)) & (log.tabela == "wms_kompletacja")].sort_values("proba")
    sygnaly.append({
        "id": "wms-1310", "obszar": "Dane", "odbiorca": "IT", "waga": "niska", "miasto": None,
        "tytul": "Zmiana schematu eksportu WMS opóźniła dane kompletacji za 13.10",
        "liczba": f"{len(wms)} próby",
        "opis": (f"Pierwsza próba zakończyła się błędem. {wms.iloc[0].komunikat_bledu} Ponowienie wystartowało "
                 f"o {pd.Timestamp(wms.iloc[-1].start_ladowania):%H:%M} i zakończyło się statusem "
                 f"{wms.iloc[-1].status}, czyli dane kompletacji były dostępne dopiero przed południem."),
        "pytanie": "Które kontrole jakości danych nie przeszły w ostatnich 7 dniach?",
        "strona": "p4DaneIT",
    })

    # ---------------------------------------------------------------- IT: ładowania i kontrole
    od14 = WCZORAJ - timedelta(days=13)
    l14 = log[log.data_biznesowa >= od14].sort_values(["data_biznesowa", "start_ladowania"])
    ladowania = [{
        "id": int(r.ladowanie_id), "d": r.data_biznesowa.isoformat(), "system": r.system_zrodlowy, "tabela": r.tabela,
        "start": pd.Timestamp(r.start_ladowania).strftime("%Y-%m-%dT%H:%M"),
        "min": float(r.czas_trwania_min), "zal": int(r.wiersze_zaladowane), "ocz": int(r.wiersze_oczekiwane),
        "status": r.status, "blad": None if pd.isna(r.komunikat_bledu) else r.komunikat_bledu, "proba": int(r.proba)} for r in l14.itertuples()]

    kj = rd("it_kontrola_jakosci")
    kj["data_biznesowa"] = pd.to_datetime(kj.data_biznesowa).dt.date
    kj_bad = kj[kj.wynik != "Zaliczona"].sort_values("data_biznesowa", ascending=False)
    kontrole = [{"d": r.data_biznesowa.isoformat(), "system": r.system_zrodlowy, "tabela": r.tabela,
                 "kontrola": r.kontrola, "wynik": r.wynik, "bledne": int(r.bledne_wiersze)}
                for r in kj_bad.itertuples()]

    out = {
        "meta": {"dzis": DZIS.isoformat(), "wczoraj": WCZORAJ.isoformat(),
                 "od": min(zam.d).isoformat(), "do": max(zam.d).isoformat(),
                 "uwaga": "Dane syntetyczne przygotowane na potrzeby demonstracji. Nie są danymi żadnej rzeczywistej firmy."},
        "miasta": [{"id": r.miasto_id, "nazwa": r.miasto, "mag": r.magazyn_id} for r in miasto.itertuples()],
        "magazyny": [{"id": r.magazyn_id, "nazwa": r.magazyn} for r in magazyn.itertuples()],
        "przyczyny": {r.przyczyna_spoznienia_kod: r.przyczyna_spoznienia for r in p_sp.itertuples()},
        "przyczynyOdpisu": {r.przyczyna_odpisu_kod: r.przyczyna_odpisu for r in p_od.itertuples()},
        "dzienne": dzienne,
        "odpisy": odpisy,
        "przyczyny7": przyczyny7,
        "sygnaly": sygnaly,
        "ladowania": ladowania,
        "kontrole": kontrole,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":"), allow_nan=False), encoding="utf-8")

    # zgodność z liczbami kontrolnymi z lakehouse i modelu
    kontrolne = json.loads((DATA / "_kontrolne.json").read_text(encoding="utf-8"))
    pom = sum(r["pomiar"] for r in dzienne)
    pk = sum(r["punkt"] for r in dzienne)
    chk = {
        "zamowienia": (sum(r["zam"] for r in dzienne), kontrolne["zamowienia"]),
        "linie": (sum(r["linie"] for r in dzienne), kontrolne["linie"]),
        "punktualnosc_pct": (round(100 * pk / pom, 2), kontrolne["punktualnosc_pct"]),
        "braki_pct": (round(100 * sum(r["linieBrak"] for r in dzienne) / sum(r["linie"] for r in dzienne), 2),
                      kontrolne["braki_pct"]),
        "odpisy_wartosc": (round(sum(r["wart"] for r in odpisy), 2), kontrolne["odpisy_wartosc"]),
    }
    ok = True
    for k, (a, b) in chk.items():
        good = abs(a - b) < 0.02
        ok &= good
        print(f"{k:18} snapshot={a}  kontrolne={b}  {'OK' if good else 'ROZBIEZNOSC'}")
    print(f"sygnały: {len(sygnaly)}, ładowania: {len(ladowania)}, kontrole: {len(kontrole)}, "
          f"rozmiar: {OUT.stat().st_size / 1024:.0f} KB")
    for s in sygnaly:
        print(f"- [{s['odbiorca']}] {s['tytul']} | {s['liczba']}\n    {s['opis']}")
    if not ok:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
