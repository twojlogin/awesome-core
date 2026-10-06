#!/usr/bin/env python3
"""core/bootstrap.py — sam przygotowujemy środowisko, żeby nikt nie musiał.

Wymaganie właściciela: „nie każ mi pisać python -m venv, source
venv/bin/activate, pip install". Poprawne, bo to trzy kroki, na których
ludzie się wywalają, a porażka wygląda jak „program zepsuty".

Ten moduł:
  1. sprawdza, czy Flask już jest (CLI i TUI działają bez niego),
  2. jeśli nie ma — tworzy venv i instaluje requirements.txt,
  3. mówi w dokładnie której linii co robi, bo to kilka sekund na GitHubie,
  4. podaje ścieżkę do interpretera, który ma Flask.

Nic nie działa w tle i nic nie jest instalowane bez wypisanego komunikatu.
"""

import os
import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
REQUIREMENTS = BASE_DIR / "requirements.txt"
VENV_DIR = BASE_DIR / "venv"
GUARD_ENV = "AWESOME_NO_VENV_RETRY"


def has_flask(interpreter=None):
    """Czy ten interpreter widzi flask. Sprawdzone uruchomieniem, nie zgadywane."""
    exe = interpreter or sys.executable
    try:
        done = subprocess.run(
            [str(exe), "-c", "import flask"], capture_output=True, timeout=30
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return done.returncode == 0


def venv_python():
    if os.name == "nt":
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python"


def _run(command, label):
    print(f"  {label}…", flush=True)
    done = subprocess.run(command, capture_output=True, text=True)
    if done.returncode != 0:
        tail = (done.stderr or done.stdout or "").strip().splitlines()
        print(f"  Nie udało się: {tail[-1] if tail else 'nieznany błąd'}")
        return False
    return True


def ensure_flask_interpreter(verbose=True):
    """Zwraca interpreter z flask (albo None). Nigdy nie wywala się wyjątkiem."""
    if has_flask():
        return Path(sys.executable)
    existing = venv_python()
    if existing.exists() and has_flask(existing):
        if verbose:
            print(f"  Flask już jest w {VENV_DIR.name}/")
        return existing
    if os.environ.get(GUARD_ENV):
        if verbose:
            print("  Mam już jedną próbę za sobą i nadal nie ma Flaska — "
                  "sprawdź wyjście powyżej.")
        return None

    if verbose:
        print(f"\nWeb UI potrzebuje Flaska. Przygotowuję środowisko "
              f"({REQUIREMENTS.name}):")
    if not existing.parent.exists() and not VENV_DIR.exists():
        if not _run([sys.executable, "-m", "venv", str(VENV_DIR)],
                    "Tworzę venv"):
            return None
    if not _run([str(venv_python()), "-m", "pip", "install", "--upgrade", "pip"],
                "Aktualizuję pip"):
        return None
    if not _run([str(venv_python()), "-m", "pip", "install", "-r", str(REQUIREMENTS)],
                "Instaluję z requirements.txt"):
        return None
    if not has_flask(venv_python()):
        if verbose:
            print("  Flask dalej nie importuje się — sprawdź sieć albo proxy.")
        return None
    if verbose:
        print(f"  Gotowe. Od teraz web używa {VENV_DIR.name}/.\n")
    return venv_python()


def relaunch_with_flask(restart=None):
    """Przekaż sterowanie do interpretera z flask, albo wyjaśnij dlaczego nie."""
    target = ensure_flask_interpreter()
    if target is None or Path(target).resolve() == Path(sys.executable).resolve():
        return False
    if restart is None:
        restart = [Path(__file__).resolve().parent.parent / "cli" / "awesome_cli.py"]
    env = dict(os.environ, **{GUARD_ENV: "1"})
    print(f"  Przełączam się na {target}", flush=True)
    try:
        os.execve(str(target), [str(target), *map(str, restart), *sys.argv[1:]], env)
    except OSError as exc:
        print(f"  Nie dało się przełączyć interpretera: {exc}")
        return False
    return True