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
# trzeba je odtworzyć w trakcie builda: najpierw pobranie list z GitHuba,
# potem zbudowanie bazy. Token jest opcjonalny — bez niego GitHub limituje
# wyszukiwanie, ale build i tak się kończy.
ARG GITHUB_TOKEN=""
RUN GITHUB_TOKEN="${GITHUB_TOKEN}" python3 core/fetcher.py awesome-list \
    && python3 extract_tools.py

# Serwer MCP czyta gotową bazę i mówi czystym JSON-RPC 2.0 po stdio.
# Logi lecą na stderr, więc nie psują kanału protokołu.
ENTRYPOINT ["python3", "-u", "core/mcp.py"]
