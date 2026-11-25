"""Generator danych syntetycznych do demo analityki konwersacyjnej Northwind Traders.

Northwind Traders to fikcyjny sklep internetowy z dostawa zakupow spozywczych vanem.
Wszystkie dane (miasta obslugi, magazyny, wolumeny, dostawcy, marki, produkty, zdarzenia)
sa wymyslone na potrzeby demo.

Uzycie:
    python generate_data.py            # zapis do data/*.parquet
"""
from __future__ import annotations

import json
import zlib
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "data"
OUT.mkdir(exist_ok=True)

rng = np.random.default_rng(2026)

START = date(2026, 8, 3)
END = date(2026, 10, 27)          # ostatni dzien biznesowy; "dzis" w scenariuszu = 28.10.2026
TODAY = date(2026, 10, 28)

# ------------------------------------------------------------------ wymiary

MAGAZYNY = [
    ("LUB", "Centrum dystrybucyjne Lublin", "Fikcyjny"),
    ("RZE", "Magazyn Rzeszów (demo)", "Fikcyjny"),
    ("OLS", "Magazyn Olsztyn (demo)", "Fikcyjny"),
]

# miasto_id, miasto, magazyn, udzial w wolumenie, minuty dojazdu z magazynu
MIASTA = [
    ("LUB", "Lublin", "LUB", 0.34, 30),
    ("ZAM", "Zamość", "LUB", 0.10, 100),
    ("RZE", "Rzeszów", "RZE", 0.22, 30),
    ("PRZ", "Przemyśl", "RZE", 0.08, 80),
    ("OLS", "Olsztyn", "OLS", 0.18, 30),
    ("ELB", "Elbląg", "OLS", 0.08, 90),
]

STREFY = {
    "LUB": ["Śródmieście", "Czechów", "Czuby", "Kalinowszczyzna", "Wrotków", "Felin"],
    "ZAM": ["Stare Miasto", "Karolówka", "Planty", "Nowe Miasto"],
    "RZE": ["Śródmieście", "Baranówka", "Pobitno", "Drabinianka", "Słocina"],
    "PRZ": ["Zasanie", "Lipowica", "Kmiecie"],
    "OLS": ["Śródmieście", "Jaroty", "Zatorze", "Kortowo", "Dajtki"],
    "ELB": ["Śródmieście", "Zawada", "Nad Jarem"],
}

OKNA = list(range(6, 22, 2))  # okna 2-godzinne 06-08 ... 20-22
OKNO_WAGI = np.array([6, 12, 9, 8, 14, 21, 18, 13], dtype=float)


def pora_dnia(h: int) -> str:
    if h < 10:
        return "Rano"
    if h < 15:
        return "Południe"
    if h < 19:
        return "Popołudnie"
    return "Wieczór"


PRZYCZYNY_SPOZNIENIA = [
    ("KOREK", "Korki na trasie"),
    ("WYJAZD", "Opóźniony wyjazd z magazynu"),
    ("DOJAZD", "Długi dojazd z magazynu do miasta"),
    ("AWARIA", "Awaria pojazdu"),
    ("POGODA", "Warunki pogodowe"),
    ("KLIENT", "Brak kontaktu z klientem"),
    ("ADRES", "Problem z adresem lub dostępem"),
]

PRZYCZYNY_ODPISU = [
    ("TERMIN", "Przeterminowanie"),
    ("USZKODZENIE", "Uszkodzenie w magazynie"),
    ("TEMPERATURA", "Przerwanie łańcucha chłodniczego"),
    ("JAKOSC_PRZYJECIE", "Niska jakość przy przyjęciu"),
    ("ZWROT", "Zwrot od klienta"),
]

# kategoria -> (strefa temperaturowa, udzial w liniach, p. braku, odpis jako udzial sprzedazy, podkategorie)
KATEGORIE = {
    "Owoce i warzywa": ("Chłodzona", 0.17, 0.025, 0.030, {
        "Owoce jagodowe": ["Truskawki", "Borówki amerykańskie", "Maliny", "Jeżyny"],
        "Owoce": ["Jabłka Ligol", "Banany", "Gruszki Konferencja", "Mandarynki", "Winogrona białe"],
        "Warzywa": ["Pomidory malinowe", "Ogórki gruntowe", "Papryka czerwona", "Marchew", "Ziemniaki młode",
                    "Sałata masłowa", "Brokuł", "Cebula żółta"],
    }),
    "Nabiał": ("Chłodzona", 0.15, 0.012, 0.010, {
        "Mleko": ["Mleko 2%", "Mleko 3,2%", "Mleko bez laktozy"],
        "Jogurty": ["Jogurt naturalny", "Jogurt grecki", "Kefir", "Maślanka"],
        "Sery": ["Ser żółty Gouda", "Twaróg półtłusty", "Serek wiejski", "Mozzarella"],
        "Masło i śmietana": ["Masło extra", "Śmietana 18%", "Śmietanka 30%"],
    }),
    "Mięso i ryby": ("Chłodzona", 0.08, 0.018, 0.015, {
        "Drób": ["Filet z kurczaka", "Udka z kurczaka", "Filet z indyka"],
        "Wieprzowina": ["Schab bez kości", "Karkówka", "Mięso mielone"],
        "Wędliny": ["Szynka gotowana", "Polędwica sopocka", "Kabanosy"],
        "Ryby": ["Łosoś filet", "Dorsz filet", "Śledź w oleju"],
    }),
    "Pieczywo": ("Otoczenia", 0.07, 0.020, 0.040, {
        "Chleb": ["Chleb żytni", "Chleb pszenny", "Chleb na zakwasie"],
        "Bułki": ["Bułka kajzerka", "Bułka grahamka", "Rogal maślany"],
    }),
    "Mrożonki": ("Mrożona", 0.05, 0.010, 0.003, {
        "Warzywa mrożone": ["Mieszanka warzywna", "Fasolka szparagowa", "Szpinak"],
        "Lody": ["Lody waniliowe", "Lody czekoladowe"],
        "Dania mrożone": ["Pierogi ruskie", "Pizza margherita"],
    }),
    "Napoje": ("Otoczenia", 0.13, 0.008, 0.001, {
        "Woda": ["Woda niegazowana", "Woda gazowana"],
        "Soki": ["Sok pomarańczowy", "Sok jabłkowy", "Nektar multiwitamina"],
        "Kawa i herbata": ["Kawa ziarnista", "Kawa mielona", "Herbata czarna", "Herbata zielona"],
    }),
    "Artykuły spożywcze": ("Otoczenia", 0.14, 0.008, 0.001, {
        "Makarony i ryż": ["Makaron spaghetti", "Makaron penne", "Ryż basmati"],
        "Przetwory": ["Passata pomidorowa", "Koncentrat pomidorowy", "Groszek konserwowy"],
        "Słodycze i przekąski": ["Czekolada mleczna", "Herbatniki", "Chipsy solone", "Orzechy włoskie"],
        "Śniadanie": ["Płatki owsiane", "Musli", "Dżem truskawkowy", "Miód wielokwiatowy"],
    }),
    "Chemia i dom": ("Otoczenia", 0.13, 0.006, 0.0005, {
        "Środki czystości": ["Płyn do naczyń", "Proszek do prania", "Płyn do podłóg"],
        "Higiena": ["Papier toaletowy", "Ręczniki papierowe", "Pasta do zębów", "Mydło w płynie"],
        "Dziecko": ["Pieluchy rozm. 4", "Chusteczki nawilżane"],
    }),
}

DOSTAWCY = {
    "Owoce i warzywa": ["Sad Warmiński (demo)", "Zielona Grządka (demo)", "Owocowy Gaj (demo)"],
    "Nabiał": ["Mleczarnia Dolina (demo)", "Mleczarnia Polana (demo)", "Serowar (demo)"],
    "Mięso i ryby": ["Zagroda Mięsna (demo)", "Rybna Zatoka (demo)"],
    "Pieczywo": ["Piekarnia Kłos (demo)", "Piekarnia Rogal (demo)"],
    "Mrożonki": ["Mroźna Kraina (demo)"],
    "Napoje": ["Źródło Napoje (demo)", "Palarnia Aromat (demo)"],
    "Artykuły spożywcze": ["Spiżarnia (demo)", "Słodka Chwila (demo)", "Młyn Złoty (demo)"],
    "Chemia i dom": ["Czysty Dom (demo)", "Maluch (demo)"],
}
MARKI = ["Dolina", "Polana", "Zagroda", "Kłos", "Smakosz", "Natura Plus"]
WARIANTY = {"Chłodzona": ["250 g", "500 g", "1 kg"], "Mrożona": ["450 g", "750 g", "1 kg"],
            "Otoczenia": ["opak. mniejsze", "opak. standard", "opak. rodzinne"]}

DATE_COLS = {"data", "data_dostawy", "data_biznesowa", "poczatek_tygodnia"}
BOOL_COLS = {"w_oknie", "zamiennik_odrzucony", "czy_weekend", "czy_kompletne"}


def stable_idx(text: str, n: int) -> int:
    return zlib.crc32(text.encode("utf-8")) % n


def build_products() -> tuple[pd.DataFrame, pd.DataFrame]:
    sup_rows, sid = [], 1
    sup_ids: dict[str, list[str]] = {}
    for cat, names in DOSTAWCY.items():
        for n in names:
            code = f"D{sid:03d}"
            sup_rows.append((code, n, cat))
            sup_ids.setdefault(cat, []).append(code)
            sid += 1
    dim_dostawca = pd.DataFrame(sup_rows, columns=["dostawca_id", "dostawca", "kategoria_glowna"])
    dim_dostawca["uwaga"] = "Nazwa fikcyjna"

    rows, n = [], 100001
    for cat, (temp, _share, _pb, _po, subs) in KATEGORIE.items():
        for sub, bases in subs.items():
            for base in bases:
                for marka in rng.choice(MARKI, size=3, replace=False):
                    for wariant in WARIANTY[temp]:
                        sup = sup_ids[cat][stable_idx(base + marka, len(sup_ids[cat]))]
                        # przypisania potrzebne do historii demo
                        if sub in ("Mleko", "Jogurty") and marka == "Dolina":
                            sup = "D004"
                        if cat == "Owoce i warzywa" and marka == "Zagroda":
                            sup = "D001"
                        price = float(rng.uniform(2.5, 35.0))
                        price *= 1.6 if cat == "Mięso i ryby" else 1.3 if cat == "Chemia i dom" else 1
                        rows.append((f"SKU{n}", f"{base} {marka} {wariant}", cat, sub, temp, sup, str(marka),
                                     round(price, 2)))
                        n += 1
    dim_produkt = pd.DataFrame(rows, columns=["sku_id", "produkt", "kategoria", "podkategoria",
                                              "strefa_temperaturowa", "dostawca_id", "marka", "cena"])
    return dim_produkt, dim_dostawca


def to_arrow(df: pd.DataFrame) -> pa.Table:
    cols = {}
    for c in df.columns:
        s = df[c]
        if c in BOOL_COLS:
            cols[c] = pa.array([None if v is None or (isinstance(v, float) and np.isnan(v)) else bool(v)
                                for v in s], type=pa.bool_())
        elif c in DATE_COLS:
            cols[c] = pa.array(pd.to_datetime(s).dt.date, type=pa.date32())
        elif pd.api.types.is_datetime64_any_dtype(s):
            # czas lokalny zapisany jako UTC, zeby Spark i Direct Lake nie przesuwaly godzin
            cols[c] = pa.array(s.dt.tz_localize("UTC").astype("datetime64[us, UTC]"),
                               type=pa.timestamp("us", tz="UTC"))
        elif pd.api.types.is_integer_dtype(s):
            cols[c] = pa.array(s.astype("int64"), type=pa.int64())
        elif pd.api.types.is_float_dtype(s):
            cols[c] = pa.array(s.astype("float64"), type=pa.float64(), from_pandas=True)
        else:
            cols[c] = pa.array([None if v is None or (isinstance(v, float) and np.isnan(v)) else str(v)
                                for v in s], type=pa.string())
    return pa.table(cols)


def main() -> None:
    dim_produkt, dim_dostawca = build_products()
    assert dim_dostawca.loc[dim_dostawca.dostawca_id == "D004", "dostawca"].item() == "Mleczarnia Dolina (demo)"
    assert dim_dostawca.loc[dim_dostawca.dostawca_id == "D001", "dostawca"].item() == "Sad Warmiński (demo)"

    dim_magazyn = pd.DataFrame(MAGAZYNY, columns=["magazyn_id", "magazyn", "zrodlo_opisu"])
    dim_miasto = pd.DataFrame([(m[0], m[1], m[2], m[4]) for m in MIASTA],
                              columns=["miasto_id", "miasto", "magazyn_id", "dojazd_z_magazynu_min"])
    strefy = []
    for mid, names in STREFY.items():
        miasto = next(m[1] for m in MIASTA if m[0] == mid)
        for i, s in enumerate(names, 1):
            strefy.append((f"{mid}-{i:02d}", s, miasto))
    dim_strefa = pd.DataFrame(strefy, columns=["strefa_id", "strefa", "miasto_strefy"])
    dim_okno = pd.DataFrame([(f"O{h:02d}", f"{h:02d}:00-{h + 2:02d}:00", h, pora_dnia(h)) for h in OKNA],
                            columns=["okno_id", "okno", "godzina_od", "pora_dnia"])
    dim_przyczyna_spoznienia = pd.DataFrame(PRZYCZYNY_SPOZNIENIA,
                                            columns=["przyczyna_spoznienia_kod", "przyczyna_spoznienia"])
    dim_przyczyna_odpisu = pd.DataFrame(PRZYCZYNY_ODPISU, columns=["przyczyna_odpisu_kod", "przyczyna_odpisu"])

    dni = pd.date_range(START, TODAY, freq="D")
    dn = ["poniedziałek", "wtorek", "środa", "czwartek", "piątek", "sobota", "niedziela"]
    mn = ["", "styczeń", "luty", "marzec", "kwiecień", "maj", "czerwiec", "lipiec", "sierpień",
          "wrzesień", "październik", "listopad", "grudzień"]
    dim_data = pd.DataFrame({"data": dni})
    dim_data["rok"] = dni.year
    dim_data["miesiac_nr"] = dni.month
    dim_data["miesiac"] = [mn[m] for m in dni.month]
    dim_data["tydzien_iso"] = dni.isocalendar().week.astype(int).values
    dim_data["poczatek_tygodnia"] = dni - pd.to_timedelta(dni.weekday, unit="D")
    dim_data["tydzien"] = [f"Tydz. {w} (od {d.strftime('%d.%m')})"
                           for w, d in zip(dim_data.tydzien_iso, dim_data.poczatek_tygodnia)]
    dim_data["dzien_tygodnia_nr"] = dni.weekday + 1
    dim_data["dzien_tygodnia"] = [dn[w] for w in dni.weekday]
    dim_data["czy_weekend"] = dni.weekday >= 5

    # ------------------------------------------------------------- zamowienia
    dow_f = np.array([1.15, 1.0, 1.0, 1.05, 1.2, 0.95, 0.3])
    orders = []
    oid = 1
    biz_days = pd.date_range(START, END, freq="D")
    for d in biz_days:
        trend = 1 + 0.10 * (d - pd.Timestamp(START)).days / 90
        for mid, _m, mag, share, _dj in MIASTA:
            n = rng.poisson(1100 * share * dow_f[d.weekday()] * trend)
            if n == 0:
                continue
            zones = [s[0] for s in strefy if s[0].startswith(mid)]
            orders.append(pd.DataFrame({
                "zamowienie_id": np.arange(oid, oid + n),
                "data_dostawy": d,
                "miasto_id": mid,
                "magazyn_id": mag,
                "strefa_id": rng.choice(zones, n),
                "godzina_od": rng.choice(OKNA, n, p=OKNO_WAGI / OKNO_WAGI.sum()),
                "kanal": rng.choice(["Aplikacja", "Strona www"], n, p=[0.68, 0.32]),
                "segment_klienta": rng.choice(["Nowy", "Powracający", "Stały"], n, p=[0.12, 0.38, 0.50]),
            }))
            oid += n
    zam = pd.concat(orders, ignore_index=True)
    zam["okno_id"] = "O" + zam.godzina_od.map("{:02d}".format)

    # ------------------------------------------------------------- kursy
    zam = zam.sort_values(["data_dostawy", "miasto_id", "godzina_od", "strefa_id"]).reset_index(drop=True)
    zam["kurs_seq"] = zam.groupby(["data_dostawy", "miasto_id"]).cumcount() // 16
    zam["kurs_id"] = ("K-" + zam.data_dostawy.dt.strftime("%y%m%d") + "-"
                      + zam.miasto_id + "-" + (zam.kurs_seq + 1).map("{:02d}".format))
    zam["nr_przystanku"] = zam.groupby("kurs_id").cumcount() + 1
    dojazd = {m[0]: m[4] for m in MIASTA}

    kurs = zam.groupby("kurs_id").agg(data=("data_dostawy", "first"), miasto_id=("miasto_id", "first"),
                                      magazyn_id=("magazyn_id", "first"), przystanki=("zamowienie_id", "size"),
                                      pierwsze_okno=("godzina_od", "min")).reset_index()
    nk = len(kurs)
    kurs["pojazd"] = ["VAN-" + str(v) for v in rng.integers(100, 400, nk)]
    kurs["kierowca"] = ["KR-" + str(v) for v in rng.integers(1000, 1600, nk)]
    kurs["planowany_wyjazd"] = kurs.data + pd.to_timedelta(
        kurs.pierwsze_okno * 60 - kurs.miasto_id.map(dojazd) - 10, unit="m")
    wyj_delay = rng.exponential(5, nk)
    # 28.09-02.10: zator w kompletacji w centrum Lublin, pozne poranne wyjazdy
    zator = ((kurs.magazyn_id == "LUB") & (kurs.data >= "2026-09-28") & (kurs.data <= "2026-10-02")
             & (kurs.pierwsze_okno <= 8)).values
    wyj_delay = np.where(zator, wyj_delay + rng.uniform(20, 45, nk), wyj_delay)
    kurs["opoznienie_wyjazdu_min"] = np.round(wyj_delay, 0).astype(int)
    kurs["faktyczny_wyjazd"] = kurs.planowany_wyjazd + pd.to_timedelta(kurs.opoznienie_wyjazdu_min, unit="m")
    kurs["km_plan"] = np.round(kurs.miasto_id.map(dojazd).values * 1.1 * 2
                               + kurs.przystanki.values * rng.uniform(2.5, 4.0, nk), 1)

    awaria_ids = set(kurs[(kurs.miasto_id == "OLS") & (kurs.data == "2026-09-23")]
                     .sample(2, random_state=7).kurs_id)
    zam = zam.merge(kurs[["kurs_id", "opoznienie_wyjazdu_min"]], on="kurs_id", how="left")

    # ------------------------------------------------------------- punktualnosc
    n = len(zam)
    dts = zam.data_dostawy
    krk_pop = ((zam.miasto_id == "RZE") & (zam.godzina_od == 16)).values
    ldz_rano = ((zam.miasto_id == "ZAM") & (zam.godzina_od == 6)).values
    deszcz = ((dts >= "2026-10-12") & (dts <= "2026-10-16")).values
    pozny_wyjazd = (zam.opoznienie_wyjazdu_min > 15).values
    awaria = zam.kurs_id.isin(awaria_ids).values
    p = 0.045 + 0.003 * zam.nr_przystanku.values
    p = p + 0.15 * krk_pop + 0.14 * ldz_rano + 0.07 * deszcz + 0.25 * pozny_wyjazd
    p = np.where(awaria, 0.95, p)
    late = rng.random(n) < np.clip(p, 0, 0.98)

    reason = rng.choice(["KOREK", "WYJAZD", "KLIENT", "ADRES", "POGODA", "DOJAZD"], n,
                        p=[0.36, 0.14, 0.22, 0.16, 0.06, 0.06]).astype(object)
    u = rng.random(n)
    reason = np.where(krk_pop & (u < 0.75), "KOREK", reason)
    reason = np.where(ldz_rano & (u < 0.70), "DOJAZD", reason)
    reason = np.where(deszcz & (u > 0.45), "POGODA", reason)
    reason = np.where(pozny_wyjazd & (u < 0.8), "WYJAZD", reason)
    reason = np.where(awaria, "AWARIA", reason)
    reason = np.where(late, reason, None)

    late_min = np.where(awaria, rng.uniform(55, 140, n), 4 + rng.exponential(17, n))
    okno_od = dts + pd.to_timedelta(zam.godzina_od, unit="h")
    okno_do = okno_od + pd.Timedelta(hours=2)
    arrival = np.where(late, okno_do + pd.to_timedelta(late_min, unit="m"),
                       okno_od + pd.to_timedelta(rng.uniform(1, 118, n), unit="m"))
    zam["okno_od"] = okno_od
    zam["okno_do"] = okno_do
    zam["dostarczono_o"] = pd.to_datetime(arrival).floor("min")
    zam["w_oknie"] = pd.Series(~late, dtype=object)
    zam["minuty_spoznienia"] = np.where(late, np.round(late_min, 0), 0).astype(float)
    zam["przyczyna_spoznienia_kod"] = reason
    zam["status_dostawy"] = "Dostarczono"

    # luka TMS: 27.10 brak zdarzen dostaw dla Olsztyna i Elbląga
    gap = (zam.data_dostawy == pd.Timestamp(END)) & zam.miasto_id.isin(["OLS", "ELB"])
    zam.loc[gap, "dostarczono_o"] = pd.NaT
    zam.loc[gap, "w_oknie"] = None
    zam.loc[gap, "minuty_spoznienia"] = np.nan
    zam.loc[gap, "przyczyna_spoznienia_kod"] = None
    zam.loc[gap, "status_dostawy"] = "Brak danych z TMS"

    # ------------------------------------------------------------- linie
    nl = 6 + rng.poisson(18, len(zam))
    lin_idx = np.repeat(np.arange(len(zam)), nl)
    lin_oid = zam.zamowienie_id.values[lin_idx]
    starts = np.repeat(np.cumsum(nl) - nl, nl)
    nr = np.arange(len(lin_idx)) - starts + 1

    cat_share = {c: v[1] for c, v in KATEGORIE.items()}
    w = (dim_produkt.kategoria.map(cat_share).values
         / dim_produkt.groupby("kategoria").sku_id.transform("size").values)
    w = w * (rng.pareto(2.5, len(w)) + 0.2)
    w = w / w.sum()
    sku_i = rng.choice(len(dim_produkt), len(lin_idx), p=w)
    kat = dim_produkt.kategoria.values[sku_i]
    dost = dim_produkt.dostawca_id.values[sku_i]
    price = dim_produkt.cena.values[sku_i]
    L = len(lin_idx)
    qty = 1 + rng.poisson(0.6, L)

    l_date = pd.DatetimeIndex(zam.data_dostawy.values[lin_idx])
    l_mag = zam.magazyn_id.values[lin_idx]
    pb = pd.Series(kat).map({c: v[2] for c, v in KATEGORIE.items()}).values.astype(float)
    dolina = (dost == "D004") & (l_date >= "2026-10-05") & (l_date <= "2026-10-11")
    pb = np.where(dolina, 0.22, pb)
    pb = np.where((kat == "Pieczywo") & (l_date.weekday == 5), pb + 0.07, pb)
    krk_cool = ((l_mag == "RZE") & np.isin(kat, ["Nabiał", "Mięso i ryby"])
                & (l_date >= "2026-10-07") & (l_date <= "2026-10-08"))
    pb = np.where(krk_cool, pb + 0.16, pb)
    event = rng.random(L) < pb
    r2 = rng.random(L)
    braki_reason = np.where(r2 < 0.12, "USZKODZENIE", np.where(r2 < 0.22, "KRÓTKI_TERMIN", "BRAK_STANU"))
    braki_reason = np.where(krk_cool, "BLOKADA_JAKOŚCIOWA", braki_reason)
    braki_reason = np.where(dolina, "BRAK_STANU", braki_reason)

    sub = event & (kat != "Chemia i dom") & (rng.random(L) < 0.55)
    partial = event & ~sub & (qty > 1) & (rng.random(L) < 0.35)
    missing = event & ~sub & ~partial
    status = np.where(sub, "Zamiennik", np.where(partial, "Częściowa", np.where(missing, "Brak", "Kompletna")))
    rejected = sub & (rng.random(L) < np.where(kat == "Nabiał", 0.20, 0.11))
    wydana = np.where(missing, 0, np.where(partial, np.maximum(qty - 1 - rng.integers(0, 2, L), 0), qty))
    wydana = np.where(rejected, 0, wydana)
    lines = pd.DataFrame({
        "zamowienie_id": lin_oid,
        "linia_nr": nr,
        "sku_id": dim_produkt.sku_id.values[sku_i],
        "ilosc_zamowiona": qty,
        "ilosc_wydana": wydana,
        "status_linii": status,
        "przyczyna_braku": np.where(event, braki_reason, None),
        "zamiennik_odrzucony": pd.Series(np.where(sub, rejected, None), dtype=object),
        "cena_jedn": price,
    })
    lines["wartosc_zamowiona"] = np.round(lines.ilosc_zamowiona * price, 2)
    lines["wartosc_wydana"] = np.round(lines.ilosc_wydana * price, 2)
    lines["wartosc_utracona"] = np.round(lines.wartosc_zamowiona - lines.wartosc_wydana, 2)

    lines["_nk"] = (status != "Kompletna").astype(int)
    agg = lines.groupby("zamowienie_id").agg(wartosc_zamowienia=("wartosc_zamowiona", "sum"),
                                             liczba_linii=("linia_nr", "size"),
                                             linie_niekompletne=("_nk", "sum"))
    lines = lines.drop(columns="_nk")
    zam = zam.merge(agg, on="zamowienie_id", how="left")
    zam["wartosc_zamowienia"] = zam.wartosc_zamowienia.round(2)
    zam["czy_kompletne"] = zam.linie_niekompletne == 0

    # ------------------------------------------------------------- odpisy
    sold = (pd.DataFrame({"data": l_date, "magazyn_id": l_mag, "sku_id": lines.sku_id.values, "ilosc": wydana})
            .groupby(["data", "magazyn_id", "sku_id"], as_index=False).ilosc.sum())
    sold = sold.merge(dim_produkt[["sku_id", "kategoria", "podkategoria", "dostawca_id", "cena",
                                   "strefa_temperaturowa"]], on="sku_id")
    rate = sold.kategoria.map({c: v[3] for c, v in KATEGORIE.items()}).values.astype(float)
    jag_aug = ((sold.podkategoria == "Owoce jagodowe") & (sold.data.dt.month == 8)).values
    rate = np.where(jag_aug, 0.10, rate)
    sad = ((sold.dostawca_id == "D001") & (sold.magazyn_id == "OLS")
           & (sold.data >= "2026-09-07") & (sold.data <= "2026-09-20")).values
    rate = np.where(sad, rate * 5, rate)
    cool = ((sold.magazyn_id == "RZE") & sold.kategoria.isin(["Nabiał", "Mięso i ryby"])
            & (sold.data == "2026-10-07")).values
    lam = sold.ilosc.values * rate * rng.lognormal(0, 0.35, len(sold))
    lam = np.where(cool, sold.ilosc.values * 1.8 + 2, lam)
    q = rng.poisson(lam)
    keep = q > 0
    od = sold[keep]
    rr = rng.random(len(od))
    chl = (od.strefa_temperaturowa == "Chłodzona").values
    base_r = np.where(rr < 0.55, "TERMIN", np.where(rr < 0.78, "USZKODZENIE",
                      np.where(rr < 0.88, "ZWROT", np.where(chl, "TEMPERATURA", "USZKODZENIE"))))
    base_r = np.where(jag_aug[keep] & (rr < 0.8), "TERMIN", base_r)
    base_r = np.where(sad[keep] & (rr < 0.8), "JAKOSC_PRZYJECIE", base_r)
    base_r = np.where(cool[keep], "TEMPERATURA", base_r)
    fact_odpis = pd.DataFrame({
        "data": od.data.values, "magazyn_id": od.magazyn_id.values, "sku_id": od.sku_id.values,
        "przyczyna_odpisu_kod": base_r, "ilosc": q[keep],
        "wartosc_kosztowa": np.round(q[keep] * od.cena.values * 0.72, 2),
    })

    # ------------------------------------------------------------- IT: log ladowan i kontrole jakosci
    ld = pd.Series(l_date.date)
    per_day = {
        ("SKLEP", "sklep_zamowienia"): zam.groupby(zam.data_dostawy.dt.date).size(),
        ("SKLEP", "sklep_linie_zamowien"): ld.value_counts(),
        ("WMS", "wms_kompletacja"): ld.value_counts(),
        ("WMS", "wms_stany_magazynowe"): pd.Series(len(dim_produkt) * 4, index=biz_days.date),
        ("TMS", "tms_kursy"): kurs.groupby(kurs.data.dt.date).size(),
        ("TMS", "tms_zdarzenia_dostaw"): zam.groupby(zam.data_dostawy.dt.date).size(),
        ("ERP", "erp_odpisy"): fact_odpis.groupby(pd.to_datetime(fact_odpis.data).dt.date).size(),
    }
    start_h = {"SKLEP": 2.0, "WMS": 2.5, "TMS": 3.0, "ERP": 4.0}
    logs, checks, lid = [], [], 1
    tms_ok_27 = int(((zam.data_dostawy == pd.Timestamp(END)) & ~gap).sum())
    for d in biz_days.date:
        run_day = pd.Timestamp(d) + pd.Timedelta(days=1)
        for (sysn, tbl), s in per_day.items():
            exp_rows = int(s.get(d, 0))
            st = run_day + pd.Timedelta(hours=start_h[sysn], minutes=float(rng.uniform(0, 20)))
            dur = float(rng.uniform(3, 14)) * (2.5 if tbl in ("sklep_linie_zamowien", "wms_kompletacja") else 1)
            loaded, status, err, attempt = exp_rows, "Sukces", None, 1
            if d == END and tbl == "tms_zdarzenia_dostaw":
                loaded, status, dur = tms_ok_27, "Częściowy", 41.0
                err = "Przekroczony czas odpowiedzi API TMS po 3 próbach. Brak zdarzeń dla miast: Olsztyn, Elbląg."
            if d == date(2026, 10, 13) and tbl == "wms_kompletacja":
                logs.append((lid, d, sysn, tbl, st, st + pd.Timedelta(minutes=2), 0, exp_rows, "Błąd",
                             "Niezgodność schematu: nowa kolumna 'strefa_buforowa' w eksporcie WMS.", 1))
                lid += 1
                st, dur, attempt = run_day + pd.Timedelta(hours=9, minutes=21), 19.0, 2
            end_ts = st + pd.Timedelta(minutes=dur)
            logs.append((lid, d, sysn, tbl, st, end_ts, loaded, exp_rows, status, err, attempt))
            lid += 1

            for chk in ["Zgodność liczby wierszy ze źródłem", "Unikalność klucza", "Kompletność kluczy obcych",
                        "Świeżość danych"]:
                c_status, bad = "Zaliczona", 0
                if chk == "Zgodność liczby wierszy ze źródłem" and loaded < exp_rows:
                    c_status, bad = "Niezaliczona", exp_rows - loaded
                if chk == "Unikalność klucza" and d == date(2026, 9, 29) and tbl == "sklep_linie_zamowien":
                    c_status, bad = "Niezaliczona", 1284
                if chk == "Świeżość danych" and d == date(2026, 10, 13) and tbl == "wms_kompletacja":
                    c_status = "Ostrzeżenie"
                if chk == "Kompletność kluczy obcych" and tbl == "erp_odpisy" and rng.random() < 0.03:
                    c_status, bad = "Ostrzeżenie", int(rng.integers(1, 6))
                checks.append((d, sysn, tbl, chk, c_status, bad, end_ts + pd.Timedelta(minutes=2)))
    it_log = pd.DataFrame(logs, columns=["ladowanie_id", "data_biznesowa", "system_zrodlowy", "tabela",
                                         "start_ladowania", "koniec_ladowania", "wiersze_zaladowane",
                                         "wiersze_oczekiwane", "status", "komunikat_bledu", "proba"])
    it_log["czas_trwania_min"] = ((it_log.koniec_ladowania - it_log.start_ladowania)
                                  .dt.total_seconds() / 60).round(1)
    it_kontrola = pd.DataFrame(checks, columns=["data_biznesowa", "system_zrodlowy", "tabela", "kontrola",
                                                "wynik", "bledne_wiersze", "wykonano_o"])

    # ------------------------------------------------------------- zapis
    fact_zam = zam[["zamowienie_id", "data_dostawy", "miasto_id", "strefa_id", "okno_id", "kurs_id",
                    "nr_przystanku", "kanal", "segment_klienta", "wartosc_zamowienia", "liczba_linii",
                    "czy_kompletne", "okno_od", "okno_do", "dostarczono_o", "w_oknie", "minuty_spoznienia",
                    "przyczyna_spoznienia_kod", "status_dostawy"]].copy()
    fact_kurs = kurs[["kurs_id", "data", "miasto_id", "pojazd", "kierowca", "przystanki", "planowany_wyjazd",
                      "faktyczny_wyjazd", "opoznienie_wyjazdu_min", "km_plan"]].copy()

    tables = {
        "dim_data": dim_data, "dim_magazyn": dim_magazyn, "dim_miasto": dim_miasto, "dim_strefa": dim_strefa,
        "dim_okno": dim_okno, "dim_produkt": dim_produkt, "dim_dostawca": dim_dostawca,
        "dim_przyczyna_spoznienia": dim_przyczyna_spoznienia, "dim_przyczyna_odpisu": dim_przyczyna_odpisu,
        "fact_zamowienie": fact_zam, "fact_linia_zamowienia": lines, "fact_kurs": fact_kurs,
        "fact_odpis": fact_odpis, "it_log_ladowan": it_log, "it_kontrola_jakosci": it_kontrola,
    }
    schemas = {}
    for name, df in tables.items():
        t = to_arrow(df)
        pq.write_table(t, OUT / f"{name}.parquet", compression="snappy")
        schemas[name] = [{"name": f.name, "type": str(f.type)} for f in t.schema]
        print(f"{name:<28} {t.num_rows:>10,} wierszy  {(OUT / f'{name}.parquet').stat().st_size / 1e6:6.1f} MB")
    (OUT / "_schemas.json").write_text(json.dumps(schemas, indent=2, ensure_ascii=False), encoding="utf-8")

    valid = fact_zam[fact_zam.w_oknie.notna()]
    ctrl = {
        "zamowienia": int(len(fact_zam)),
        "linie": int(len(lines)),
        "punktualnosc_pct": round(float(valid.w_oknie.astype(bool).mean() * 100), 2),
        "braki_pct": round(float((lines.status_linii == "Brak").mean() * 100), 2),
        "odpisy_wartosc": round(float(fact_odpis.wartosc_kosztowa.sum()), 2),
        "it_ladowania_niepelne": int((it_log.status != "Sukces").sum()),
    }
    (OUT / "_kontrolne.json").write_text(json.dumps(ctrl, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(ctrl, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
