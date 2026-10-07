# Arek — security automation for Linux & Windows

Buduję narzędzia do bezpieczeństwa i automatyzacji: skanery, recon, hardening,
skrypty PowerShell do Windowsa i katalogi narzędzi, które działają **lokalnie
i offline**. Kod w Pythonie, PowerShellu i bashu. Bez usług w chmurze, bez
telemetrycznych zależności, bez licencji za dostęp.

Główne projekty:

| Projekt | Co to robi | Status |
|---|---|---|
| **[awesome-core](https://github.com/twojlogin/awesome-core)** | Katalog narzędzi z awesome list — 186 861 narzędzi z 829 list, ranking oparty o zgodę niezależnych kuratorów. CLI, TUI, Web, MCP. Python stdlib + jedna zależność. | ✅ publiczne |
| `ArekBox-Installer` | Modularny menadżer zestawów narzędzi na Linuksie — jeden skrypt, bez zależności
| `security-rocket` | Hardening Linuksa w bashu: SSH, UFW, AppArmor, sysctl, AIDE — z preflightem, backupem i rollbackiem
| `WindowsToolkit-Pro` | Skrypty PowerShell do Windowsa: bezpieczeństwo, optymalizacja, setup
| `matrix-command` | Dashboard reconu bezpieczeństwa: backend FastAPI + interfejs webowy
| `softhunt` | Wyszukiwanie i odkrywanie oprogramowania między platformami

Linki do projektów po migracji pojawią się tutaj.

---

## awesome-core — co to dowodzi

**Problem:** GitHub ma tysiące „awesome list", które powielają te same
narzędzia. Sortowanie po gwiazdkach listy premiuje listy z dobrym README, nie
dobre narzędzia.

**Rozwiązanie:** ranking liczony z **zgody niezależnych kuratorów** — ile
różnych autorów list wskazało to samo narzędzia — plus jakość listy i prawdziwe
gwiazdki repozytorium, pobrane z API GitHuba. Wszystko liczone jawnie, każdą
punktację da się rozłożyć (`awesome why nmap`).

**Skala i inżynieria:**

- **186 861 narzędzi** z **829 list** (1 032 pobrane), 215 327 wzmianek, 81 języków
- **SQLite + FTS5** zamiast plików JSON — 171 MB danych, milisekundowe
  wyszukiwanie (3–16 ms), indeksy i transakcje, żeby przerwany build nie
  zniszczył bazy
- **Własny parser Markdown** (linki, tabele, badge'e, kod) + filtr śmieci:
  19 300 odrzuconych pozycji (reklamy, artykuły, sklepy, martwe subdomeny)
- **Detekcja kopii list**: trzy listy kopiujące jedną to nie trzy niezależne
  opinie, więc kopie nie liczą się do zgody kuratorów (próg 80% nakładania)
- **Wykrywanie zatrucia katalogu**: 0 gwiazdek przy setkach linków, setki
  linków do jednego właściciela, martwe linki, domeny-podróżki
  (`github.com@evil.tld`, `githvb.com`)
- **Bezpieczeństwo danych z obcych źródeł**: opisy z cudzych repozytoriów
  przechodzą przez filtr prompt-injection, zanim trafią do kontekstu modelu
- **Serwer MCP** (JSON-RPC po stdio) jako źródło narzędzi dla lokalnych agentów —
  jedyne wejście AI, łatwo odłączalne; rdzeń to czysty stdlib
- **Wydajność zmierzona, nie zgadnięta**: build 300 s → 100 s po analizie
  (jeden regex okazał się 11× wolniejszy niż oryginał i został wycofany)
- **105 testów**, CI na Pythonie 3.8–3.12, jedna zależność zewnętrzna (Flask)
- **Zero kroków konfiguracji**: od `git clone` do pierwszego wyniku — jedno
  polecenie; brak Flaska, `jq`, `curl` i GitHub CLI nie blokuje pracy, a
  `./awesome doctor` odpowiada, co dokładnie jest nie tak

```bash
git clone https://github.com/twojlogin/awesome-core.git
cd awesome-core && ./awesome start          # 10–25 min, potem offline
./awesome search "port scanner" --os windows
./awesome why nmap                          # dlaczego to jest wysoko
```

Dokumentacja (PL/EN), w tym **model zagrożeń** i granice tego, czego system nie
wykrywa: [README](https://github.com/twojlogin/awesome-core#readme)

---

## Jak pracuję

- **Najpierw pomiar, potem twierdzenie.** Każdą optymalizację mierzę i podaję
  liczby z obu stron — także wtedy, gdy wynik jest gorszy niż był.
- **Weryfikuję na czystej maszynie, nie na swojej.** Nowy kod sprawdzam w
  świeżym klonie, bez swoich plików i bez logowania.
- **Nie zostawiam pytań zamiast odpowiedzi.** Każdy błąd kończy się komunikatem
  z komendą do wpisania, nie pytaniem „czy ktoś wie, jak to naprawić".
- **Test ma łapać regresję**, nie dokumentować, że coś działa.
- **Nie polecam niczego.** Pokazuję liczby i filtry o jawnych kryteriach;
  decyzja zostaje po stronie użytkownika.

## Kontakt

GitHub: [twojlogin](https://github.com/twojlogin) ·
profil: [twojlogin.github.io](https://twojlogin.github.io/)

<!--
  Kopia profilu GitHub (twojlogin/twojlogin). Trzymam ją tutaj, żeby dało się
  edytować bez przeglądarki. Aby wrzucić zmiany na profil:

      cp profile/README.md /tmp/profrepo/README.md
      cd /tmp/profrepo && git add README.md && git commit -m "profil" && git push
-->
