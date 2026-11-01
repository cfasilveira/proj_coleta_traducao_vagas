# ADEM Job Scraper & Translator

A modular pipeline that extracts job offers from the Luxembourg ADEM JobBoard, translates them to Brazilian Portuguese, and archives the results in a human-readable text file.

The project evolved from a single monolithic script into four reusable modules, each with a single responsibility, driven by a clear engineering philosophy: **Early Return, Fail First, Fail Gracefully, and Logs/Auditing throughout**.

---

## Table of Contents

- [Project Evolution](#project-evolution)
- [Engineering Philosophy](#engineering-philosophy)
- [Architecture](#architecture)
- [API Protection Strategy](#api-protection-strategy)
- [Module Contracts](#module-contracts)
- [Installation](#installation)
- [Usage](#usage)
- [Auditing](#auditing)
- [Future Improvements](#future-improvements)

---

## Project Evolution

### Phase 1: Monolithic Script

The initial version was a single `main.py` that performed three tasks sequentially:

1. Opened a Chromium browser via **Playwright** and scraped job offers from the ADEM website.
2. Translated each offer using **`deep-translator`** (Google Translate wrapper).
3. Wrote the result to `ofertas_Luxemburgo.txt`.

**Problems encountered:**

| Problem | Root Cause | Symptom |
|---|---|---|
| `Timeout exceeded` waiting for selectors | Site is JavaScript-rendered | Script aborted before finding any offer |
| `429 Too Many Requests` from Google | `deep-translator` uses a plain HTTP client that Google flags as a bot | Every translation failed, file was saved with original (untranslated) text |
| No visibility into what failed | No structured logging | User had to read a Python traceback to understand what went wrong |
| Whole pipeline crashes on a single bad offer | No error isolation | One network hiccup discarded all extracted data |

### Phase 2: Modular Architecture

The monolithic script was refactored into **four independent modules**, each with a single responsibility:

```
adem_scraper/
├── main.py                  # Orchestrator (pipeline)
├── auditor.py               # Centralized logging & auditing
├── extrator_adem.py         # Playwright: extraction
├── tradutor_texto.py        # googletrans-curl: translation
├── gerenciador_arquivo.py   # aiofiles: atomic file writing
└── pyproject.toml
```

**Why modularize?**

- **Reusability:** The translation and archiving modules are site-agnostic. A future scraper for a different job board can reuse them untouched.
- **Testability:** Each module can be tested in isolation (e.g., mock a text string and verify the translator output).
- **Maintainability:** A change in Google's rate-limit policy only touches `tradutor_texto.py`. A layout change on the ADEM website only touches `extrator_adem.py`.
- **Separation of Concerns:** The orchestrator (`main.py`) doesn't know *how* Playwright works or *which* translation library is used. It only knows the contracts.

---

## Engineering Philosophy

Every module follows four rules:

### 1. Early Return

Return as soon as the outcome is known, avoiding deeply nested conditionals.

```python
# gerenciador_arquivo.py
if not ofertas:
    auditor.warning("arquivo", "Nenhuma oferta recebida.")
    return True
```

### 2. Fail First

Detect unrecoverable conditions *before* doing expensive work.

```python
# extrator_adem.py
try:
    browser = await p.chromium.launch(headless=False)
except PlaywrightError as e:
    auditor.fatal("extrator", f"Falha ao abrir navegador: {e}")
    return None  # abort the pipeline immediately
```

### 3. Fail Gracefully

A failure in one item must not destroy the whole batch.

```python
# extrator_adem.py
for url in urls:
    try:
        await page.goto(url)
        # ...
    except PlaywrightTimeoutError:
        auditor.error("extrator", f"Timeout em {url}. Pulando.")
        # continue to the next offer
```

### 4. Logs and Auditing Throughout

Every module sends structured messages to `auditor.py`, which writes to both the terminal (real-time feedback) and `execucao.log` (persistent audit trail) with timestamps and severity levels.

```python
auditor.info("extrator", f"Extraindo {len(urls)} ofertas...")
auditor.warning("tradutor", "Tradução retornou vazia.")
auditor.error("arquivo", f"Falha de I/O: {e}")
auditor.estouro_caracteres(
    "tradutor", f"Texto com {len(texto)} caracteres excede o limite."
)
auditor.fatal("main", "Extração falhou criticamente. Abortando.")
```

---

## Architecture

```
┌──────────────┐    list[dict]    ┌──────────────┐   list[dict]   ┌───────────────────┐
│ extrator_    │ ───────────────► │  main.py     │ ─────────────► │ gerenciador_      │
│ adem.py      │                  │ (orquestra)  │                │ arquivo.py        │
└──────────────┘                  └──────┬───────┘                └───────────────────┘
                                         │
                                         │ (str)
                                         ▼
                                  ┌──────────────┐
                                  │ tradutor_    │
                                  │ texto.py     │
                                  └──────────────┘
                                         │
                                         │ (todos os módulos)
                                         ▼
                                  ┌──────────────┐
                                  │ auditor.py   │ ──► terminal + execucao.log
                                  └──────────────┘
```

---

## API Protection Strategy

Free translation APIs (Google's unofficial web endpoint, which `googletrans-curl` wraps) have two hard limits:

1. **~5,000 characters per request** — beyond this, the API truncates or errors.
2. **Rate limits** — too many requests in a short window trigger `429 Too Many Requests`.

To keep the MVP under control and avoid burning the API budget on pathological inputs, we implemented three defense layers:

### Layer 1: Character Limit (Hard Cap)

```python
# tradutor_texto.py
LIMITE_CARACTERES = 4000

if len(texto) > LIMITE_CARACTERES:
    auditor.estouro_caracteres("tradutor", f"Texto com {len(texto)} caracteres...")
    return False, texto, False  # non-retryable
```

Texts exceeding **4,000 characters** are **not sent to the API**. They are flagged with the custom `[ESTOURO_CARACTERES]` category and archived as "not translated" (only title and URL are saved, per policy).

> **Why 4,000?** Google's web endpoint starts failing around 5,000 chars in practice. 4,000 leaves a 20% safety margin.

### Layer 2: Progressive Retry Buffer

If a translation fails for a **transient** reason (network glitch, rate limit), the offer is moved to a retry buffer instead of being discarded.

```python
# main.py
for tentativa, espera in enumerate(ESPERA_ENTRE_RETRIES, start=1):
    if not buffer_retry:
        break
    await asyncio.sleep(espera)  # 30s, then 60s, then 120s
    for oferta in buffer_retry:
        sucesso, texto, retentavel = await traduzir(oferta["texto"])
        ...
```

**Total worst-case wait:** `30 + 60 + 120 = 210 seconds` across three rounds — enough for Google to lift a short-lived IP block.

### Layer 3: Differentiated Failure Semantics

Each translation call returns a **3-tuple**: `(sucesso, texto, retentavel)`.

| Scenario | Return | Retry? |
|---|---|---|
| Success | `(True, translated, False)` | No |
| Empty text | `(True, "", False)` | No |
| Character overflow | `(False, original, False)` | **No** (text won't shrink) |
| Rate limit / network | `(False, original, True)` | **Yes** |
| Unknown error | `(False, original, True)` | **Yes** |

This prevents the retry buffer from wasting up to 210 seconds per oversized offer — a purely semantic improvement that saves both time and API calls.

---

## Module Contracts

### `auditor.py`

| Function | Level | Purpose |
|---|---|---|
| `info(mod, msg)` | INFO | Normal progress |
| `warning(mod, msg)` | WARNING | Recoverable anomaly |
| `error(mod, msg)` | ERROR | Non-blocking failure |
| `critical(mod, msg)` | CRITICAL | Serious failure requiring attention |
| `fatal(mod, msg)` | CRITICAL | Pipeline will abort |
| `estouro_caracteres(mod, msg)` | WARNING | **Custom category:** text exceeds MVP limit |

Outputs to **both** `stdout` (real-time, `HH:MM:SS`) and `execucao.log` (persistent, full timestamp).

### `extrator_adem.py`

- **Input:** none (uses internal `BASE_URL` and `LINK_SELECTORS`)
- **Output:** `list[dict]` where each dict is `{"url": str, "titulo": str, "texto": str}`, or `None` on fatal failure
- **Fail First:** browser launch failure → `None`
- **Early Return:** no links found → `[]` (different from `None`)
- **Fall Gracefully:** per-offer errors → `ERROR` log and continue

### `tradutor_texto.py`

- **Input:** `texto: str`
- **Output:** `tuple[bool, str, bool]` — see [Layer 3](#layer-3-differentiated-failure-semantics)
- **Fail First:** rate limit on *first* translation of the session → `CRITICAL`
- **Early Return:** empty text → `(True, "", False)`
- **Hard cap:** >4,000 chars → `(False, original, False)` + `[ESTOURO_CARACTERES]` log

### `gerenciador_arquivo.py`

- **Input:** `list[dict]`
- **Output:** `bool` (True on success)
- **Fail First:** `PermissionError` → `FATAL`, return `False`
- **Early Return:** empty list → return `True` without creating a file
- **Atomic write:** content is written to `*.tmp` then `os.replace()`d, so a mid-write failure never leaves a truncated file

---

## Installation

This project uses **[uv](https://github.com/astral-sh/uv)** for dependency management.

```bash
# Clone the repository
git clone https://github.com/cfasilveira/proj_coleta_traducao_vagas.git
cd proj_coleta_traducao_vagas

# Create the virtual environment and install dependencies
uv sync

# Install the Playwright browser (Chromium only)
uv run playwright install chromium
```

---

## Usage

```bash
uv run main.py
```

Monitor the log in real-time from another terminal:

```bash
tail -f execucao.log
```

### Output

- **`ofertas_Luxemburgo.txt`** — the human-readable archive (only created on success)
- **`execucao.log`** — the full audit trail with timestamps and severity levels
- **`debug_page.html`** — only generated when no offers are found (useful for adjusting selectors)

### Interpreting the final summary

```
============================
CONCLUÍDO | total=20 | traduzidas=18 | falhas=2
============================
```

A `falhas > 0` count combined with `grep ESTOURO_CARACTERES execucao.log` tells you whether the failures were character overflows (expected, by policy) or real errors.

---

## Auditing

The log is structured so that each concern can be isolated with `grep`:

```bash
# How many offers were discarded for being too long?
grep ESTOURO_CARACTERES execucao.log

# Were there Google rate-limit blocks?
grep "Rate limit" execucao.log

# Which individual offers failed to extract?
grep "\[EXTRATOR" execucao.log | grep ERROR

# Full timeline of the last run
cat execucao.log
```

---

## Future Improvements

- **Parallel extraction:** use multiple Playwright pages within the same browser context to speed up the `goto()` loop (currently sequential, ~3s per offer).
- **Configurable character limit:** move `LIMITE_CARACTERES` to a `.env` file or CLI argument.
- **Chunking for long texts:** split texts above the limit into ~4,500-char chunks at `\n` boundaries and concatenate the translations (rejected for the MVP, but a natural next step).
- **Official translation API:** swap `googletrans-curl` for Google Cloud Translation (paid, but with clear quotas and no bot detection).
- **Unit tests:** add `pytest` coverage for `tradutor_texto.py` (mocked responses) and `gerenciador_arquivo.py` (temp directories).
```
