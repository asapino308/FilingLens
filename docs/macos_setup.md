# FilingLens setup on macOS

This is the shortest supported path from a GitHub download to a working FilingLens installation. The financial-analysis features do not require a local language model; LM Studio or Ollama is optional for Ask the Filing and Analyst Brief.

## 1. Check the Mac

Recommended for the documented 12B model path:

- Apple Silicon Mac;
- macOS 14 or newer;
- 16 GB or more unified memory;
- roughly 12-15 GB of free space for the repository, Python environment, caches, and one 7-8 GB model.

LM Studio officially recommends 16 GB or more RAM on Apple Silicon. Ollama supports macOS 14+ on Apple Silicon and supports Intel Macs in CPU-only mode. On an 8 GB Mac, choose a smaller model and a modest context window.

## 2. Install Python

Check the existing version:

```bash
python3 --version
```

FilingLens requires Python 3.11 or newer. If needed, install a current macOS build from [python.org](https://www.python.org/downloads/macos/) or with Homebrew:

```bash
brew install python@3.12
```

Homebrew is optional; do not install it solely for FilingLens if `python3 --version` already reports 3.11 or newer.

## 3. Download and install FilingLens

```bash
git clone https://github.com/asapino308/FilingLens.git
cd FilingLens
./scripts/setup_macos.sh
```

If macOS says the script cannot be executed:

```bash
chmod +x scripts/setup_macos.sh
./scripts/setup_macos.sh
```

The setup helper creates an isolated `.venv`, installs all runtime packages from `pyproject.toml`, and creates `.env` without overwriting an existing one.

## 4. Configure SEC access

Open `.env` in a text editor and change:

```dotenv
SEC_USER_AGENT=FilingLens/1.0 your-email@example.com
```

to an address you monitor. The SEC uses this header to contact automated clients when necessary. The `.env` file is ignored by Git and the doctor never prints the value, but the address is transmitted to SEC.gov with requests.

## 5. Choose a local AI service

### LM Studio

LM Studio is the easiest option for users who prefer a graphical model manager.

1. Download [LM Studio](https://lmstudio.ai/download) and open it once.
2. In Discover, search for **Gemma 4 12B**.
3. On Apple Silicon with 16-24 GB memory, choose the MLX 5-bit build (approximately 7.7 GB). A smaller Gemma 4 E2B/E4B model is safer on an 8 GB Mac.
4. Load the model with an initial context of 16K-32K. Very large contexts consume substantially more memory and FilingLens retrieves only a few relevant passages.
5. Open Developer and start the server on port `1234`. Keep network serving disabled unless you deliberately need it.
6. Keep `LOCAL_LLM_PROVIDER=auto` or set it to `lmstudio` in `.env`.

Verify:

```bash
curl http://127.0.0.1:1234/v1/models
```

LM Studio can also be controlled after first launch with:

```bash
lms ls
lms load
lms server start
```

FilingLens leaves `LMSTUDIO_MODEL` blank by default and uses the model ID returned by the server. If authentication is enabled in LM Studio, place the local token in `LMSTUDIO_API_KEY`; never commit `.env`.

### Ollama

Ollama is useful for a mostly terminal-based workflow.

1. Download [Ollama for macOS](https://ollama.com/download), install it in Applications, and open it.
2. On Apple Silicon, run:

```bash
ollama run gemma4:12b-mlx
```

The comparable portable tag is `gemma4:12b`. Smaller Macs can start with `gemma4:e2b-mlx`.

3. Type `/bye` to leave the initial chat.
4. Set `LOCAL_LLM_PROVIDER=ollama` in `.env` if LM Studio may also be running.

Verify:

```bash
curl http://127.0.0.1:11434/api/tags
```

FilingLens uses Ollama's native `/api/chat` endpoint with `think=false` for completion-safe answers and reports token/latency metadata when available.

## 6. Run diagnostics and launch

```bash
.venv/bin/python scripts/doctor.py
.venv/bin/python -m streamlit run app.py
```

Open the displayed address, normally `http://localhost:8501`. You can also double-click `Launch FilingLens.command` after setup. Stop the terminal launch with `Control+C`.

## 7. First-use test

1. Enter `AAPL`.
2. Confirm that Overview shows company details and annual metrics.
3. Open Ask the Filing and load the latest 10-K.
4. Ask: `What factors did management say affected revenue?`
5. Confirm that the answer contains `[Source N]` markers and inspect every displayed passage.

The first SEC request may take longer because the cache is empty. The first model response may also be slow while the model loads.

## Troubleshooting

### Python is too old

Install Python 3.11+ and rerun setup with an explicit executable:

```bash
PYTHON_BIN=python3.12 ./scripts/setup_macos.sh
```

### `SEC_USER_AGENT` error

The `.env` file is missing, still contains the example address, or does not include an email. Run `cp .env.example .env`, edit it, and restart FilingLens.

### LM Studio is not detected

- Confirm the Developer server is running on port `1234`.
- Run `curl http://127.0.0.1:1234/v1/models`.
- Confirm `LMSTUDIO_BASE_URL=http://127.0.0.1:1234/v1`.
- If JIT loading is disabled, load a chat model before starting FilingLens.

### Ollama is not detected

- Open the Ollama app.
- Run `curl http://127.0.0.1:11434/api/tags`.
- Download a model with `ollama run gemma4:12b-mlx`.
- Confirm `OLLAMA_BASE_URL=http://127.0.0.1:11434`.

### Model response times out

Use a smaller model, reduce the model's context length, close memory-heavy applications, or increase the provider timeout in `.env`. A timeout affects only local generation; SEC data and deterministic analytics remain available.

### Start over safely

Delete only the local `.venv` directory, recreate it with `./scripts/setup_macos.sh`, and keep `.env` if its settings are correct. SEC cache files under `data/cache/` can be removed if you want a fresh download; they are not required for the repository.

## Official references

- [LM Studio system requirements](https://lmstudio.ai/docs/app/system-requirements)
- [LM Studio local-server quickstart](https://lmstudio.ai/docs/developer/rest/quickstart)
- [LM Studio CLI](https://lmstudio.ai/docs/cli)
- [Ollama macOS requirements](https://docs.ollama.com/macos)
- [Ollama API chat endpoint](https://docs.ollama.com/api/chat)
- [Ollama Gemma 4 models](https://ollama.com/library/gemma4)
