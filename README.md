# JOB-HUNTER

Wyszukiwarka ofert pracy firm, **które nie publikują swoich ofert na jobboardach** — działająca w 100% lokalnie.

> Notatka rozbudowana o: opis techniczny (pkt 3), pomysły na zwiększenie zasięgu wyszukiwania (pkt 5), roadmapę i listę decyzji do podjęcia. Pierwotne sekcje zachowane w pkt 1, 2 i 4.

## 1. Co chcemy osiągnąć
Wyszukiwarka ofert pracy firm, które nie publikują swoich ofert na jobboardach.

## 2. Opis projektu — fundament MVP
1. Strona www działająca lokalnie.
2. Strona wyszukuje w Google (za pomocą różnych zapytań) strony firmowe prowadzące do zakładki kariery.
3. Strona wyświetla wyniki w formie czytelnej listy z możliwością zaznaczenia danego rekordu jako „aplikowano".

### Założenia MVP
- **Rynek**: Polska (domeny `.pl` + polskie frazy) z przełącznikiem „rynek globalny" w konfiguracji.
- **Użytkownik**: jedna osoba, bez logowania — całość działa lokalnie.
- **Stan**: SQLite — oferty, statusy i historia przetrwają między sesjami.
- **Pętla użycia**: słowa kluczowe → „Szukaj" → lista ofert/stron kariery → odsiewanie → oznaczenie „aplikowano".

## 3. Architektura techniczna

### Stack (decyzja: Python/FastAPI + React/Vite)
| Warstwa | Technologia | Rola |
|---|---|---|
| Backend | **Python 3.12** (instalowany przez `uv`; systemowy Python 3.9 Apple na macOS 27 pada z SIGSEGV/SIGBUS przy lxml), **FastAPI** | lokalne API na `http://localhost:8000` |
| HTTP/parsowanie | **httpx** + **BeautifulSoup4** | SERP-y i strony kariery (HTML statyczny) |
| Strony JS-rendered | **Playwright** (headless Chromium) | strony kariery zbudowane w React/Vue; wyrywkowo (drogo wydajnościowo) |
| Baza | **SQLite** (plik `jobhunter.db`) | firmy, oferty, statusy, historia zapytań |
| Frontend | **React + Vite + TypeScript + Mantine (UI)** | `localhost:5173` — AppShell (sidebar+header), zakładki, karty, tabele |
| Testy | **pytest** | query builder, parser, dedupe |

### Struktura projektu
```
backend/
  app/
    main.py                 # FastAPI — start aplikacji
    config.py               # .env: TLD, wykluczenia, limity, klucze Google
    search/
      query_builder.py      # generator puli zapytań (szablony × słowa × filtry)
      meta_ddgs.py          # darmowe silniki ddgs z backendem: google_free / bing / yahoo / brave
      duckduckgo.py         # duckduckgo (backend ddgs "duckduckgo")
      google_scrape.py      # scrapowanie SERP Google — awaryjne, domyślnie OFF
      normalizer.py         # dedupe, czyszczenie utm, normalizacja URL
    crawler/
      fetcher.py            # pobieranie stron (httpx; Playwright gdy trzeba JS)
      career_page.py        # wykrywanie linków do ofert na stronie kariery
      jsonld.py             # ekstrakcja JSON-LD "@type": "JobPosting"
      ats.py                # publiczne API ATS (Greenhouse/Lever/… — patrz pomysł nr 6)
    storage/
      db.py, models.py      # SQLite + modele
  tests/
frontend/                   # React + Vite
```

### Przepływ danych
1. **Query builder** buduje pulę zapytań z szablonów: słowa kariery × słowa kluczowe × TLD × miasto × wykluczenia jobboardów.
2. **Search client** wykonuje zapytania przez darmowe silniki ddgs (`google_free`, `duckduckgo`, `bing`…) z twardymi limitami czasu (20 s/zapytanie, 75 s/sesja) i pauzą między zapytaniami.
3. **Normalizer**: dedupe (znormalizowany URL bez parametrów śledzenia), przypisanie do domeny firmy.
4. **Crawler** dla nowych domen wchodzi na `/kariera`, `/careers` i wyciąga listy ofert: linki do podstron, `JSON-LD JobPosting`, API ATS. Działa ręcznie („Odśwież" w UI) i **automatycznie po każdym wyszukiwaniu** (auto-crawl, maks. N firm — przełącznik w UI).
5. **UI**: lista ofert (firma, tytuł, miasto, źródło, data pierwszego ujrzenia) + statusy (`nowa / obejrzana / aplikowano / odrzucona`) + wyszukiwanie i filtry.

### Źródła wyników (stan po zmianach Google 2026)
Google wycofało przełącznik „Search the entire web" dla NOWYCH wyszukiwarek PSE, więc **silnik Google CSE (API) został usunięty z aplikacji** (klucze/budżet/diagnostyka — historia w gicie). Źródła wyników:
- `google_free` — **Google przez darmowy backend `ddgs`** (bez kluczy, bez projektu Cloud, bez limitu 100/dzień) — domyślne,
- `duckduckgo` / `bing` / `brave` / `yahoo` — darmowe backendy `ddgs` (przejściowo bywają kapryśne),
- `google_scrape` — bezpośrednie scrapowanie SERP Google (awaryjne, domyślnie OFF — narusza ToS),
- `career_page` — bezpośrednie wejście na stronę kariery firmy (auto-crawl) — najcenniejsze źródło.

### Endpointy API (MVP)
- `POST /api/search` — uruchamia wyszukiwanie **w tle** (body: `keywords[]`, `tld`, `engines[]`, `max_queries`, `date_restrict`, `auto_crawl`) i od razu zwraca `search_id`
- `GET /api/search/{id}` — status/postęp/podsumowanie wyszukiwania
- `GET /api/offers` — lista z filtrami `?status=&q=&source=&company=&language=&text_lang=`
- `PATCH /api/offers/{id}` — status (`nowa|obejrzana|aplikowano|odrzucona`) i notatka; `DELETE /api/offers/{id}` — usuwanie wpisu
- `GET /api/exclusions` + `POST/DELETE` — lista wykluczonych domen (z natychmiastowym czyszczeniem)
- `GET /api/companies` oraz `POST /api/companies/{id}/refresh` — wejście na stronę kariery firmy i odświeżenie jej ofert
- `GET /api/export.csv` — eksport do śledzenia aplikacji
- `GET /api/queries` — historia zapytań

### Model danych (SQLite)
```
Company:    id, domain, name, first_seen, last_seen, source_query
Offer:      id, company_id→Company, title, url, location, salary,
            languages, text_lang, source, first_seen, last_seen, status, notes
QueryLog:   id, query, engine, created_at, results_count, http_status
Exclusions: id, domain, added_at, source ('default'/'user')
```
Dedupe oferty = hash z pary (domena, znormalizowany URL). Pola `first_seen`/`last_seen` pozwalają odróżnić „nowe" od „już znanych" ofert.

## 4. Przykładowe zapytania (oryginał + rozbudowa)
1. `site:*.pl (kariera OR careers) software developer` *(oryginalne — otwórz w Google)*
2. `(inurl:career OR inurl:careers OR inurl:kariera) (React OR frontend OR TypeScript) -site:linkedin.com -site:pracuj.pl -site:justjoin.it` *(oryginalne)*
3. `intitle:(kariera OR careers OR jobs OR praca) (Python OR Java OR ".NET" OR "data engineer") -site:pracuj.pl -site:justjoin.it -site:linkedin.com`
4. `inurl:(kariera OR careers OR jobs OR praca OR rekrutacja OR join-us) (remote OR Kraków OR Wrocław) -site:linkedin.com`
5. `("dołącz do nas" OR "pracuj z nami" OR "otwieramy rekrutację") (backend OR frontend) site:pl`
6. `inurl:kariera (QA OR tester OR "data analyst") -site:pracuj.pl -site:justjoin.it`

> **Uwaga techniczna**: Google obsługuje wildcardy w `site:` tylko częściowo — `site:*.pl` to filtr przybliżony. Warto testować też wariant `site:.pl` oraz ograniczenia `lr=lang_pl` (język) i `gl=pl` (lokalizacja).

## 5. Pomysły: jak zwiększyć zasięg wyszukiwania

1. **Pula zapytań zamiast pojedynczego zapytania** — generator łączy szablony × słowa kluczowe × TLD × miasto × wykluczenia i wykonuje je po kolei; wyniki sklejają się w jedną deduplikowaną listę. Więcej kombinacji = więcej trafień.
2. **Więcej operatorów niż `inurl:`** — część firm nie ma słowa „kariera" w URL, ale ma je w `<title>` (`intitle:`, `allintitle:`) albo w treści (`intext:`). Zbiór słów PL/EN: `kariera | kariery | careers | jobs | praca | rekrutacja | join-us`, frazy: `"dołącz do nas"`, `"pracuj z nami"`, `"otwieramy rekrutację"`.
3. **Konfigurowalna lista wykluczeń** (rozbudowa Twoich trzech): jobboardy (linkedin, pracuj.pl, justjoin.it, rocketjobs, nofluffjobs, theprotocol, bulldogjob, praca.pl, 4programmers, indeed, glassdoor) **+ agregatory** (upwork, toptal, turing, simplyhired, jooble, geeksforgeeks, arc.dev, builtin.com, remote.co i in.). Domyślna lista w kodzie; docelowo edytowalna w UI/DB.
4. **TLD bez sztywnego `site:*.pl`** — polskie firmy mają też `.io / .eu / .com / .dev`; wykonuj równolegle wersję z filtrem TLD i bez niego (hałas ogranicza `lr=lang_pl`).
5. **Filtr świeżości** — silniki ddgs dostają parametr `timelimit` (`w` = ostatni tydzień, `m` = miesiąc), a scrapowany SERP Google `tbs=qdr:w` — od razu widzisz **nowe** oferty, zamiast ręcznie odsiewać stare.
6. **Faza 2 — crawler strony kariery + publiczne API ATS (największy zysk)**: gdy Google wskazuje domenę firmy, nie kończysz na „ta firma ma stronę kariery", tylko wchodzisz na nią i:
   - czytasz **JSON-LD** z `"@type": "JobPosting"` (uniwersalny standard osadzony wprost w HTML),
   - wykrywasz ATS z publicznymi endpointami JSON z kompletnymi listami ofert:
     - Greenhouse: `boards-api.greenhouse.io/v1/boards/{token}/jobs`
     - Lever: `api.lever.co/v0/postings/{firma}`
     - SmartRecruiters: `api.smartrecruiters.com/v1/companies/{firma}/postings`
     - Recruitee: `{firma}.recruitee.com/api/offers/`
   - z `sitemap.xml`/`robots.txt` pobierasz podstrony z ofertami.

   Efekt: **pełna lista ofert firmy**, także tak świeżych, że Google ich jeszcze nie zaindeksował. Google pełni rolę „mapy firm"; realne źródło ofert to sama strona firmy.
7. **Kolejne darmowe źródła: Google, DuckDuckGo, Bing, Brave, Yahoo** (biblioteka `ddgs`; silnik `google_free` = Google bez kluczy — istotne, bo Google wycofało „Search the entire web" w PSE dla nowych wyszukiwarek). Indeksują w różnym rytmie — często dają firmy, których nie znajdziesz gdzie indziej; przejściowe „No results found." są normalne i raportowane per zapytanie. **Formuły dobierane pod silnik**: pełne operatory (`inurl:/intitle:`) tylko przez `google_cse`; w pozostałych (w tym `google_free`) tylko `site:` + frazy — inaczej silniki je ignorują i psują trafność.
8. **Automatyczne stronicowanie** — stronicowanie wyników (strony 2..N) dla silników ddgs: sama top-10 za mało; pula zapytań + stronicowanie daje dziesiątki trafień z jednego hasła.
9. **Seed listy firm (nie przez Google)** — podborki firm na GitHubie (np. „awesome polish companies"), listy z KRS/CEIDG → dla każdej domeny od razu droga z pomysłu nr 6. Ta ścieżka nie zależy od indeksu Google, więc nie stracisz firmy, która nigdy się w wynikach nie pojawiła.
10. **Anty-blokada (ochrona przed 429/CAPTCHA)** — pauzy między zapytaniami (domyślnie 0,4 s, konfig. w `.env`), realistyczny user-agent, twarde limity czasu (20 s/zapytanie, 75 s/sesja) widoczne w UI jako licznik postępu.
11. **Historia ofert + raport „co nowego"** — każdy URL ma `first_seen`; po każdym uruchomieniu widzisz tylko przyrost. Nie marnujesz czasu wyszukiwania na wyniki, które już znasz.
12. **(Faza 3) LLM do klasyfikacji ofert** — wyciąganie z treści: stanowisko, lokalizacja/remote, widełki, wymagany stack; dopasowanie do Twojego profilu przyspiesza przesiewanie długiej listy.

## 6. Roadmapa
1. **Faza 0 — szkielet MVP** ✅ *(zrealizowana)*: FastAPI + React (Mantine) + SQLite; słowa kluczowe → darmowe silniki (google_free/duckduckgo/bing/…) → lista → status „aplikowano".
2. **Faza 1 — automatyzacja wyszukiwania**: query builder (pula zapytań), dedupe, filtry/statusy, eksport CSV.
3. **Faza 2 — crawler stron kariery**: Playwright + JSON-LD `JobPosting` + publiczne API ATS. *(częściowo zrealizowane: JSON-LD + linki + auto-crawl po wyszukiwaniu; zostało: Playwright dla stron JS i endpointy ATS)*
4. **Faza 3 — komfort**: DuckDuckGo jako 2. źródło, raport „co nowego", automatyczne odświeżanie (cron/launchd), klasyfikacja LLM.

## 7. Ryzyka i ograniczenia
- **Silniki ddgs bywają przejściowo kapryśne** („No results found.", limity IP po serii zapytań) — nieuprawnione odpowiedzi są widoczne w UI per zapytanie; głównym źródłem zostaje Google (`google_free`).
- **Scraping Google** narusza ToS → ryzyko CAPTCHA/blokady; tylko awaryjnie i po trochu.
- **Bot-ochrony firm** (Cloudflare itp.) — pomaga Playwright z realistycznym UA i opóźnieniami; część stron pozostanie trudna do automatyzacji.
- **`site:*.pl`** — Google nie wspiera w pełni wildcardów (wyniki przybliżone).
- Nie wszystko jest w indeksie Google → dlatego pomysł nr 6 (crawler + ATS) jest najważniejszy.

## 8. Decyzje do podjęcia / pytania
- [x] ~~Wariant A (CSE API)~~ — **rozstrzygnięte: usunięte**: Google wycofało „Search the entire web" w PSE dla nowych wyszukiwarek; rolę Google przejął darmowy silnik `google_free` (ddgs).
- [ ] Czy wariant B (scraping Google SERP — `google_scrape`, z pełnymi operatorami) implementować szerzej, czy zostawić awaryjnym?
- [ ] Rynek: tylko `.pl`, czy od startu przełącznik globalny?
- [ ] Na jakie role najczęściej szukasz (frontend/backend/QA/data)? — tym zestawem zasilimy bazę słów kluczowych generatora.

## 9. Uruchomienie

### Wariant skryptowy (zalecany)
```bash
./scripts/setup.sh   # pierwsza konfiguracja: venv + zależności + backend/.env + npm install
./scripts/start.sh   # start backendu :8000 i UI :5173 w tle (logi w logs/, PID-y w .run/)
./scripts/test.sh    # testy backendu (pytest)
./scripts/stop.sh    # zatrzymanie obu serwerów
```
UI: `http://localhost:5173` · API i dokumentacja: `http://localhost:8000/docs`

### Wariant ręczny (alternatywa)
```bash
# backend
cd backend && python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env               # GOOGLE_API_KEY, GOOGLE_CX, DAILY_QUERY_BUDGET
uvicorn app.main:app --reload

# frontend (drugi terminal)
cd frontend && npm install && npm run dev   # http://localhost:5173
```