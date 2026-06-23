# OrderBench — reproduce the key-free results (validity gate, smoke tests, demo eval,
# figures/tables, and the 8-primitive stdlib validity bridge) in a pinned container.
#
#   docker build -t orderbench .
#   docker run --rm orderbench            # runs `make smoke && make bridge`
#
# Re-collecting real LLM outputs (the openai:/claude-code:/ollama: adapters) needs vendor
# keys/CLIs and is intentionally out of scope for the container.
FROM python:3.12-slim

WORKDIR /orderbench
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Sanity-check the build at image-build time: every reference is clean, every buggy leaks.
RUN python scripts/validate_all.py

CMD ["sh", "-c", "make smoke && make bridge && make reproduce-tables"]
