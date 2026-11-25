# Analityka konwersacyjna w Microsoft Fabric na przykładzie sklepu e-grocery

[English version](README.md)

Northwind Traders to fikcyjny sklep internetowy z żywnością, który dowozi zakupy vanami w sześciu miastach z trzech magazynów. Firma, magazyny, dostawcy, produkty, wolumeny i zdarzenia w tym repozytorium są wymyślone, a wszystkie dane wygenerował skrypt `generate_data.py`. Nie są to dane żadnej rzeczywistej firmy.

## Co powstaje w workspace

| Element | Nazwa | Rola |
|---|---|---|
| Lakehouse | lh_northwind_demo | 15 tabel Delta (słowniki, operacje, log IT) |
| Model semantyczny | sm_northwind_operacje | Direct Lake, 17 relacji, 32 miary KPI |
| Raport | rpt_northwind_operacje | 4 strony: Punktualność, Braki i zamienniki, Straty świeżych, Świeżość danych (IT) |
| Data Agent | agent_operacje_northwind | źródła: model i lakehouse, instrukcje po polsku, 7 przykładowych zapytań SQL |

Dzień bieżący w scenariuszu to 28.10.2026. Dane obejmują 03.08-27.10.2026.

## Przed demo

1. Wznów swoją capacity Fabric (Azure Portal albo `az resource invoke-action --action resume --ids <id capacity>`).
2. Otwórz agenta `agent_operacje_northwind` i kliknij Publish (publikacja nie jest dostępna przez API).
3. Zadaj agentowi jedno pytanie na rozgrzewkę, żeby model Direct Lake załadował się do pamięci.

## Ścieżka klikania (ok. 15 minut)

1. Raport, strona Punktualność. Macierz okno x miasto pokazuje słabe okno 16-18 w Rzeszowie i 6-8 w Zamościu. Na wykresie tygodniowym widać spadek w tygodniu 42 (deszcz) i w tygodniu 40.
2. Przejście do agenta: te same pytania zadane językiem naturalnym, bez szukania właściwego widoku.
3. Strona Braki i zamienniki: wzrost braków w tygodniu 41, dostawca Mleczarnia Dolina (demo).
4. Strona Straty świeżych: skok odpisów 7.10 w magazynie Rzeszów (przerwanie łańcucha chłodniczego), borówki i truskawki w sierpniu.
5. Strona Świeżość danych (IT): niepełne ładowanie TMS za 27.10 i błąd schematu WMS 13.10.

## Pytania do agenta

Dla COO:

- Które miasto miało najniższą punktualność w zeszłym tygodniu?
- W których oknach Rzeszów spóźnia się najczęściej i z jakiego powodu?
- Dlaczego pod koniec września spadła punktualność porannych dostaw z centrum Lublin?
- Którzy dostawcy mieli najwyższy udział braków w październiku?
- Ile odpisaliśmy w magazynie w Rzeszowie 7 października i dlaczego?
- Jak zmieniała się punktualność w Zamościu w porannych oknach?

Dla IT:

- Czy dane za wczoraj są kompletne?
- Które kontrole jakości danych nie przeszły w ostatnich 7 dniach?
- Co się stało z ładowaniem WMS 13 października?
- Ile zamówień z wczoraj nie ma danych z TMS i z których miast?

## Historie wbudowane w dane

| Okres | Co się dzieje | Gdzie to widać |
|---|---|---|
| cały okres | Rzeszów, okno 16-18, korki | Punktualność, macierz |
| cały okres | Zamość, okno 6-8, długi dojazd z centrum Lublin | Punktualność, macierz |
| 23.09 | awaria 2 vanów w Olsztynie | przyczyna AWARIA |
| 28.09-02.10 | opóźnione poranne wyjazdy z centrum Lublin | Kursy, opóźnione wyjazdy |
| 05.10-11.10 | braki Mleczarni Dolina (demo) | Braki, dostawcy |
| 07.10-08.10 | blokada jakościowa chłodzonych w Rzeszowie, odpisy TEMPERATURA 7.10 | Braki, Straty |
| 12.10-16.10 | deszcz, przyczyna POGODA | Punktualność |
| 13.10 | błąd schematu WMS, ponowienie o 09:21 | IT |
| 29.09 | zdublowane klucze w liniach zamówień (1284 wiersze) | IT, kontrole |
| 27.10 | brak zdarzeń TMS dla Olsztyna i Elbląga | IT, karta "Zamówienia bez danych z TMS" |
| sierpień | wysokie odpisy owoców jagodowych | Straty |
| 07.09-20.09 | odpisy jakościowe Sad Warmiński (demo) w Olsztynie | Straty |

## Odtworzenie

Gotowe pliki parquet są w `data\`. Generator jest deterministyczny, więc `python generate_data.py` odtwarza je w identycznej postaci.

```powershell
pip install pandas pyarrow requests pyodbc
python generate_data.py
$env:FABRIC_CAPACITY_ID = "<id capacity Fabric>"      # wymagane
$env:FABRIC_WORKSPACE_NAME = "Northwind Traders demo"  # opcjonalne
cd deploy
python 01_workspace_lakehouse.py   # workspace, lakehouse, upload, tabele Delta
python 02_semantic_model.py        # model i kontrola miar względem data\_kontrolne.json
python 03_report.py                # raport PBIR z walidacją pól
python 04_data_agent.py            # sprawdza few-shoty na SQL endpoint i wdraża agenta
```

Wymagania: Python 3.12+, ODBC Driver 18 for SQL Server, Azure CLI zalogowane (`az login`) do tenanta, w którym masz capacity Fabric z uprawnieniem do tworzenia workspace. Identyfikatory wdrożonych elementów trafiają do `.fabric\deployment.json`, który jest w `.gitignore`.

## Aplikacja "Northwind Operacje" (Rayfin)

Aplikacja webowa hostowana w Fabric, w tym samym workspace (element AppBackend `northwind-operacje`), z logowaniem kontem Fabric.

| Strona | Co pokazuje |
|---|---|
| Pulpit | KPI z wczoraj na tle średniej 28 dni, trend tygodniowy, ranking miast, przyczyny opóźnień |
| Sygnały | 7 wykrytych odchyleń z podziałem COO / IT, przyciski "Zapytaj agenta", "Raport" i "Utwórz działanie" |
| Plan działań | tablica z kolumnami Do zrobienia, W toku i Zrobione, zapis w bazie aplikacji |
| Dane i ładowania | mapa ładowań z 14 dni, potwierdzanie incydentów z komentarzem, nieudane kontrole jakości |
| Zapytaj | gotowe pytania do agenta w trzech grupach |

Odczyty pochodzą ze statycznego snapshotu `app\src\data\snapshot.json`, który `app\scripts\build_snapshot.py` liczy z tych samych plików parquet i sprawdza względem `data\_kontrolne.json`. Do bazy Rayfin trafiają tylko zapisy użytkowników, czyli działania i potwierdzenia incydentów. Tablica jest wspólna dla wszystkich zalogowanych osób.

Przeglądarka nie może wywołać Data Agenta bezpośrednio, bo aplikacja ma tylko token Rayfin. Dlatego "Zapytaj agenta" kopiuje pytanie do schowka i otwiera agenta w portalu Fabric w nowej karcie. Linki do raportu i agenta biorą identyfikatory z `app\.env` (wzór w `app\.env.example`).

```powershell
cd app
copy .env.example .env             # wpisz ID raportu i agenta
python scripts\build_snapshot.py   # po zmianie danych
npm ci
npx rayfin login --tenant <tenant>
npx rayfin up --workspace-id <workspace> --tenant <tenant> -y
npm run build
```

Przy pierwszym wdrożeniu `rayfin up` uruchom dwa razy. Pierwszy przebieg może zgłosić konflikt nazwy bazy SQL. Tworzy też `rayfin\.env`, więc dopiero potem `npm run build` wkleja endpoint backendu do bundla.

## Po demo

Wstrzymaj capacity, bo nalicza koszt także wtedy, gdy nikt z niej nie korzysta.

## Licencja

Kod i dane syntetyczne udostępniam na licencji MIT (plik `LICENSE`). Pakiety `@microsoft/rayfin-*` pobierane z npm mają własne licencje.
