# Audyt pracy AI — case study

**Kontekst:** jedna sesja pracy nad projektem `awesome-core` (katalog narzędzi
z awesome list, ~8,8k linii Pythona, 106 testów). Projekt, dokumentacja i
większość kodu napisana przez model. Poniżej — **co okazało się nieprawdziwe,
jak to zostało wykryte i co z tego wynika dla audytu kodu generowanego przez AI.**

To nie jest opowieść o „wyłapaniu błędów". Jest opisem **metody**: bo błędy
były zawsze, a istotne jest to, że zostały policzone, a nie wyczute.

---

## 1. Dokumentacja kłamała, a nikt tego nie sprawdzał

| co było napisane | rzeczywistość | jak wykryte |
|---|---|---|
| „234k+ tools from 2,047 awesome lists" w opisie repo na GitHubie | 186 861 narzędzi z 1 026 list (+26%) | porównanie z `./awesome status` |
| „32 testy (CI)" w README | 106 testów | odczyt `def test_` w kodzie |
| `/help` sugeruje `enrich --limit 20000` | limit ucinał pracę w połowie | sprawdzenie, co robi komenda |
| przykład `--lang Python --os windows` | **1 wynik**, i to śmieciowy | uruchomienie przykładu z dokumentacji |
| `awesome help`: 4 komendy bez wcięcia, 6 nieudokumentowanych | kod je obsługiwał | wyłuskanie komend z dokumentacji i uruchomienie każdej |
| `stats` liczył `?` (brak znanego języka) jako język | 82 zamiast 81 | rozjazd dwóch liczb z tej samej bazy |

**Wniosek:** dokumentacja to kod, który niczego nie wykonuje i nic nie
zwaliduje. Każdą komendę i każdą liczbę trzeba **uruchomić albo policzyć
z bazy**, nie przeczytać. Po poprawkach doszły testy, które dokumentację
porównują z rzeczywistością — liczby, komendy w helpie, spójność z bazą.

---

## 2. Martwy kod i wyciek danych w publicznym repo

Moduł `core/ai_librarian.py` opisany jako „RAG-lite, LLM tylko rankinguje”:

- importował `ai_providers` — **modułu, którego nie ma w repo** (pochodził
  z innego, prywatnego projektu), więc funkcja nie mogła działać,
- endpoint `/api/ai/ask` zwracał `503` z **bezwzględną ścieżką z katalogu
  domowego autora** (dokładny tekst pomijam, bo sam jest wyciekiem — wyłapał go
  test `test_no_private_paths_in_shipped_code`),
- funkcja była w katalogu rdzenia, choć dokumentacja mówiła, że AI wchodzi
  jednym adapterem,
- komenda `awesome ask` (LLM rekomendujący narzędzia) importowała ten usunięty
  moduł i **wywalała się `ModuleNotFoundError`** przy pierwszym użyciu.

**Dlaczego test tego nie złapał:** kontrola „rdzeń bez AI" sprawdzała importy
bibliotek zewnętrznych. Tu **żadnej nie ma** — kod sam nazwał się AI, wołał
nieistniejący moduł i był martwy. Test patrzy teraz na nazwy plików oraz na
prywatne ścieżki w całym repo.

**Wniosek:** „sprawdziłem importy" nie znaczy „sprawdziłem, czy to działa".
Trzeba pytać o **zachowanie**, nie o strukturę.

---

## 3. Model ufał temu, co napisał autor, a nie kodowi

Najgłębsza wada, wskazana przez właściciela projektu: *„czytanie README, które
może być oszukane już na początku, i czepianie się tego”*.

Zmierzone: prawdziwa **Ghidra** (80 999 gwiazdek, 5 list, score 81, Java) **nie
była w ogóle kandydatem** dla zapytania `ghidra`. Kandydatów wybierał indeks
pełnotekstowy, czyli gęstość dopasowania w **opisie** — a opis pisze autor.
Repozytoria fanowskie mają słowo „Ghidra" pięć razy w opisie i wygrywały,
zanim cokolwiek zostało policzone.

Dodatkowo premia za dopasowanie nazwy była liczona **dwa razy** dla tego samego
faktu (fraza + pętla po słowach), co dawało 192 punkty stronie o Metasploicie
z jedną listą i zerem gwiazdek — i przebijało Metasploit Framework z pięcioma
listami.

Naprawione: kandydat po nazwie poza rankingiem tekstowym, górna granica premii
za nazwę, monotoniczna hierarchia (dokładne > początek słowa > w środku).

**Granica pozostaje jawna:** 13/15 trafień na pozycji #1 dla 15 znanych
narzędzi. Dwie porażki to zawsze ten sam mechanizm — opis pisze autor, a
program nie czyta kodu repozytorium. `./awesome selfcheck` istnieje po to,
żeby ta liczba była sprawdzalna, a nie deklarowana.

---

## 4. Własne błędy modelu — i gdzie je łapał ktoś inny

| błąd | skutek | wykryte przez |
|---|---|---|
| parser brał `--out` jako nazwę pliku | powstał plik `171 MB` w katalogu roboczym, wciągnięty do repo; GitHub odrzuca pliki >100 MB | zdublowana logika w audycie, potem porównanie zawartości drzewa |
| regex „optymalizacji” 11× wolniejszy niż oryginał | 3× wolniejszy build | benchmark na 20 000 iteracji, nie oko |
| `min_consensus=0` ignorowany przez `or 2` | agent prosił „bez filtra”, dostawał filtr | test z założeniem wyniku |
| `LIMIT` przed `ORDER BY` | `sqlite3: near "ORDER"` przy `export --limit` | uruchomienie komendy z dokumentacji |
| regex wygenerował podwójną nawias w SQL | **zepsuty `build` w publicznym repo** | test, nie oko |
| mock testu parsował `page=` z `per_page=100` | testy milczały zamiast sprawdzać | sam test, ale dopiero po zobaczeniu wyników |
| ekstraktor komend obracał się w spaghetti | raportował komendy, których nie ma | sam test, po wyrzuceniu regexu na rzecz uruchamiania procesu |

**Wniosek, który kosztował najwięcej:** dwie poprawki „rankingu" zrobiłem
strojąc wagi i **dwie z trzech zamieniłem jedną porażkę na drugą**. Trzecia
naprawiła objaw, nie przyczynę. Dopiero pomiar na zewnętrznej prawdzie
pokazał, że problem leży w wyborze kandydatów, a nie w wagach.

---

## 5. Co naprawdę coś dowodziło

Rozdzielenie tego, co mierzy, od tego, co tylko wygląda jak dowód:

| typ weryfikacji | wartość |
|---|---|
| testy napisane przez tego samego modelu | **zerowa** — potwierdzają założenia autora |
| 105 zielonych testów własnego kodu | dowód regresji na konkretnych błędach, nie dowód działania |
| świeży klon na maszynie bez `gh` i bez tokena | **pełny** — zmiana środowiska, której autor nie zakładał |
| interfejs TUI uruchomiony przez `pty` | **pełny** — realny terminal, nie mock |
| benchmark z zewnętrzną prawdą (15 narzędzi → właściciel repo) | **pełny** — odpowiedź zna ktoś inny niż autor kodu |
| cudze repozytoria odpalone w izolowanym venv | **pełny** — 27 + 59 + 22 przechodzące testy napisane przez kogoś innego |

Samo zdanie z komentarza w jednym z audytowanych projektów:

> Nie jest to test „czy kod jest poprawny". Test napisany przez tego samego
> model, który napisał kod, potwierdza tylko to, co ten model już wiedział.

---

## 6. Reguły, które stąd wynikają

1. **Prawda z zewnątrz, nie własne testy.** Zbuduj listę przypadków, których
   poprawną odpowiedź zna ktoś inny, i policz trafienia.
2. **Uruchamiaj, nie czytaj.** Każdą komendę z dokumentacji uruchom i sprawdź
   kod wyjścia oraz czy nie ma tracebacka.
3. **Mierz obie strony.** „Szybciej" bez liczby przed i po jest nieprawdą.
4. **Zanim opublikujesz — sprawdź sekrety, rozmiary i zależności.** Jeden
   `git add -A` w katalogu z 109 MB środowiska wirtualnego i plikami sesji
   wywoła awarię, której nie da się odkręcić.
5. **Test ma łapać błąd, który się zdarzył.** Test „sprawdzający, że kod działa"
   jest bezwartościowy, dopóki nie złapie konkretnej awarii.
6. **Nie dostrajalaj pod własny benchmark.** Trzy próby strojenia wag pod 15
   własnych przypadków dały efekt przeciwny do zamierzonego. Brak zewnętrznej
   prawdy to brak informacji zwrotnej — nie dowód, tylko dopisek.
