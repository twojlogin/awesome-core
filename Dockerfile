FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Baza (data/awesome.db) i README list (offline-db/) są w .gitignore, więc
# build próbuje je odtworzyć. Fetch/build jest opcjonalny: środowiska CI
# (np. Glama Dockerfile test) mogą nie mieć tokena ani stabilnego dostępu do
# GitHuba. Bez bazy serwer MCP startuje, ale narzędzia katalogu zwrócą błąd
# "brak bazy" zamiast psuć cały build obrazu.
ARG GITHUB_TOKEN=""
RUN GITHUB_TOKEN="${GITHUB_TOKEN}" python3 core/fetcher.py awesome-list || echo "WARN: fetch failed, continuing without full offline-db" ; \
    python3 extract_tools.py || echo "WARN: extract_tools failed, MCP server will start without catalog db"

# Serwer MCP czyta gotową bazę i mówi czystym JSON-RPC 2.0 po stdio.
# Logi lecą na stderr, więc nie psują kanału protokołu.
ENTRYPOINT ["python3", "-u", "core/mcp.py"]
