## Account Intelligence Radar (PowerShell MVP)

This project generates an actionable **company intelligence report** for business outreach using a three-layer workflow:

- **Discovery**: Google Search via [serper.dev](https://serper.dev/) to find candidate sources
- **Decision**: DeepSeek to select the best URLs for the objective
- **Extraction**: Firecrawl Extract to produce structured facts with evidence

Outputs are saved to `reports/` as:

- **JSON** (structured + traceability)
- **Markdown** (readable summary)

## Requirements

- Windows + PowerShell
- Python **3.10+**
- API keys for:
  - serper.dev
  - DeepSeek
  - Firecrawl

## Setup

1. **Create a `.env` file from the example:**

   ```powershell
   copy .env.example .env
   ```

   Then edit `.env` and fill in your API keys.

2. **Create and activate Python virtual environment:**

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

3. **Install Python dependencies:**

   ```powershell
   pip install -r requirements.txt
   ```

4. **(Optional) If PowerShell script execution is blocked, run this in the same terminal:**

   ```powershell
   Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
   ```

5. **Run the tool:**
   ```powershell
   .\run_radar.ps1 -CompanyName "Alfanar" -Objective "Extract headquarters, business units, core products, target industries, key executives, and recent strategic initiatives. Return structured JSON."
   ```

If you omit `-CompanyName` and/or `-Objective`, the script will prompt you.

## Configuration

All configuration is via environment variables (recommended: `.env` file).

- **Required**
  - `SERPER_API_KEY`
  - `DEEPSEEK_API_KEY`
  - `FIRECRAWL_API_KEY`
- **Optional**
  - `DEEPSEEK_MODEL` (default: `deepseek-chat`)
  - `HTTP_TIMEOUT_SECONDS` (default: `30`)
  - `MAX_URLS_FOR_EXTRACTION` (default: `5`)
  - `FIRECRAWL_POLL_INTERVAL_SECONDS` (default: `2`)
  - `FIRECRAWL_MAX_POLL_SECONDS` (default: `180`)

## Output

The script writes two files to `reports/` per run:

- `<timestamp>_<company_slug>.json`
- `<timestamp>_<company_slug>.md`

The JSON and Markdown both include **evidence URLs** so that major claims can be traced to sources.

## Governance & Constraints

- No LinkedIn scraping: LinkedIn URLs are filtered out of extraction.
- No custom scraping logic outside Firecrawl: discovery uses serper.dev; acquisition/extraction uses Firecrawl.
  - This means we do not build custom crawlers or scrapers inside this project.

## Troubleshooting

- **Missing API keys**: ensure `.env` exists and contains `SERPER_API_KEY`, `DEEPSEEK_API_KEY`, `FIRECRAWL_API_KEY`.
- **DeepSeek 402**: indicates insufficient balance; the tool will fall back to heuristic URL selection when possible.

## Project Folder Structure

**Root files**

`README.md`: Setup, configuration, and run instructions.

`requirements.txt`: Python dependencies.

`.env.example`: Example environment variables (no secrets).

`run_radar.ps1`: Single PowerShell entrypoint to run the tool.

`reports/`: Output folder for JSON and Markdown reports.

**Python package (three-layer + orchestration)**

`src/airadar/__init__.py`

`src/airadar/config.py`: Load .env + constants, without logging secrets.

Discovery layer: `src/airadar/discovery_serp.py` – SerpAPI client and query helpers.

Decision layer: `src/airadar/decision_llm.py` – DeepSeek client, URL ranking/selection.

Extraction layer: `src/airadar/extraction_firecrawl.py` – Firecrawl job submission, polling, and data extraction.

Domain models: `src/airadar/models.py` – Typed structures for SERP results, selected URLs, extracted facts, and final report schema.

Report builder: `src/airadar/report_builder.py` – Assemble structured JSON + Markdown and enforce traceability.

CLI/orchestrator: `src/airadar/cli_company.py` – Command-line entry for company mode.
