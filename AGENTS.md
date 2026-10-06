# Zasady tego repozytorium

Nie lista fajnych wishlist. Zasady, które właściciel ustalił w trakcie budowy
i które trzeba egzekwować, inaczej projekt zje sam siebie.

## Stan rzeczy

Katalog narzędzi z awesome list — skala i liczby są w README, sekcja
„Co jest w środku". **Nie powielaj ich tutaj**: zestarzały się już raz
(1 026 → 1 032 list) i pilnuje tego test, nie komentarz.
Baza `data/awesome.db` jest generowana, nigdy nie w repo. Kod: ~8,8k linii
Pythona, 105 testy, jedna zależność zewnętrzna (flask, tylko web UI).

Weryfikacja stanu: `./awesome status`. Nic nie działa samo — brak cronów,
daemonów i procesów w tle.

## Zasady, których nie łamie się

**1. Rdzeń bez AI.** Ranking to jawna arytmetyka w `core/scoring.py` — da się
ją wypisać i podważyć. Zero modeli, embeddingów, sieci neuronowych, LLM-ów
w środku. AI wchodzi **jednym adapterem na brzegu**: `core/mcp.py`. Możesz go
wywalić i nic nie przestanie działać. Pilnuje tego `TestNoAIinCore` — sprawdza
importy bibliotek AI, **nazwy modułów** (bo `core/ai_librarian.py` przetrwał
samą kontrolę importów) i to, że w rdzeniu nie ma modułu z wyciekiem prywatnej
ścieżki. Nigdy nie dokładaj do `core/` niczego, co woła model.

**2. Nic z cudzego repo nie jest wykonywane.** README to dane (regex, zero
`subprocess`/`eval`). `install` = `git clone` (git nie uruchamia kodu zdalnego).
Web i renderer Markdown escapują HTML. Opisy z obcych list przechodzą przez
`core/untrusted.py`, zanim wpadną do kontekstu modelu.

**3. Mierz przed twierdzeniem.** Nie „optymalizacja", tylko pomiar. W tej
historii jeden wyglądający sprytnie regex okazał się 11× wolniejszy od
oryginału — wyłapał to benchmark na 20 000 iteracji, nie oko. Jeśli piszesz
„szybciej", podaj liczbę z obu stron.

**4. Niepisze się „na oko".** Trzy listy kopiujące jedną to nie trzy
niezależne opinie. Kopie wykrywane (`core/clones.py`, próg 80%) nie liczą się do
zgody kuratorów. Dlatego 1 kopia na ponad tysiąc list, ale mechanizm jest potrzebny
na przyszłość.

**5. Zero spaghetti.** Jeden helper zamiast czterech flag. Jeden tryt jest
lepszy niż dwa na pół. Zero `if False else`, zero komentarzy wyjaśniających
oczywistość. Reguła praktyczna: jeśli kod da się napisać w połowie linijki
inaczej, jest za długi.

**6. Śmieciowe wejście nie może dać tracebacku.** `./awesome lists --limit abc`
mówi, że nie rozumie liczby. Brak bazy mówi, co odpalić. Brak Flaska mówi, jak
go zainstalować — albo sam go instaluje (`core/bootstrap.py`).

**7. Test ma łapać regresję.** Test, który dokumentuje, że coś działa, jest
bezwartościowy. Test ma złapać konkretny błąd, który się zdarzył:
`min_consensus=0` ignorowany przez `or 2`; `LIMIT` przed `ORDER BY`;
`--out` jako ścieżka do pliku. Bugi wyłapane przez testy są tańsze niż
znalezione przez użytkownika.

**8. Katalog budujemy z cudzego, więc zakładamy zatrucie.** `core/poisoning.py`
liczy, które listy wyglądają jak rozrzucanie linków (0 gwiazdek przy wielu
narzędziach, jeden właściciel, martwe linki, klon) i które linki podszywają
się pod zaufane domeny. Pilnuje tego `TestPoisoningDetection`, który sadza
fałszywą listę i wymaga, żeby ją widział. **Nie wolno rozluźniać progów,
żeby „nie było fałszywych alarmów"** — na bazie alarmów jest 7 na 1 032 listy,
czyli mało, a na rozluźnionych było 1608 na 186k narzędzi, czyli nikt by tego
nie czytał. Nigdy nie przedstawiaj tego skanu jako gwarancji.

**9. Nigdy nie polecamy niczego.** Zasada właściciela, brzmiąca krótko:
„nigdy się nie poleca nic". Program pokazuje **co jest** i **ile tego jest** —
zgoda kuratorów, gwiazdki, jakość listy, z jakich list pochodzi — a decyzję
zostawia użytkownikowi. Żadnego „polecam", „rekomendacja", „najlepszy wybór".
Ranking to **filtrowanie po jawnych kryteriach**, nie rada. Z tego powodu usunięte
zostały: komenda `awesome ask` (LLM rekomendował narzędzia z uzasadnieniem),
`/api/ai/ask` i `core/ai_librarian.py`. Jeśli dodajesz coś, co „podpowiada",
pomyśl, czy to nie jest podpowiedź pod maską.

**10. Uczciwe liczby.** Nie zaokrąglamy w górę, nie mieszamy narzędzi
z repozytoriami, nie nazywamy 3 206 martwych repo „udanymi". `status` mówi
„repozytoriów do odpytania", nie „narzędzi bez gwiazdek" — bo ponad 75 tys. wpisów to
artykuły i filmy, których gwiazdek nie da się mieć.

## Git i tożsamość

- Autor: `Arek <twojlogin@users.noreply.github.com>`
- Repo: `https://github.com/twojlogin/awesome-core` (publiczne)
- Stare repo `technoporada/awesome-core` — usunięte 6 października 2026.
  **Nie przywracamy i nie linkujemy do niego.**
- Pushujemy tylko to, co przeszło testy: `python3 tests/smoke_test.py` i CI gate.

## Czego nie robimy

- Nie dodajemy zależności bez powodu. Rdzeń = stdlib, flask = web UI.
- Nie robimy „inteligentnego" rankingu, dopóki właściciel nie powie.
- Nie publikujemy danych (baza, README cudzych list) — `data/` i `offline-db/`
  są w `.gitignore`.
- Nie kasujemy użytkownikowi bazy ani katalogu domowego. `install` ma guard
  przeciw wyjściu poza katalog instalacji.

## Jak sprawdzić, czy nie zepsuliśmy

```bash
python3 tests/smoke_test.py      # 105 testy, ~35 s
python3 -m flake8 --select=E9,F63,F7,F82 --max-line-length=120 core/ cli/ web/ tests/
./awesome status                 # stan danych i co ewentualnie odświeżyć
./awesome untrusted              # skan opisów pod prompt injection
./awesome audit                  # listy i linki, które mogą zatruć katalog
```
