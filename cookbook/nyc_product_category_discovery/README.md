# NYC Product Category Discovery

A self-contained LiteLLM cookbook application for deciding **what to validate selling** through appointment pickup and delivery in the Bronx and Queens. It standardizes market records, enforces evidence-linked model outputs, calculates a deterministic opportunity ranking, and ships with a 20-case offline evaluation suite.

## What this system can and cannot decide

The system can rank candidate categories when the same run contains:

1. fresh category-level demand data for a borough;
2. a fresh, completed supply query for that category and borough;
3. traceable observation IDs and source lineage for both observations; and
4. at least two comparable categories under the default configuration.

It returns `insufficient_data` instead of guessing when any requirement is absent. Population is context, not category demand. A low competitor count is not evidence of an underserved market unless the supply query completed. DCWP licenses cover only activities requiring a DCWP license and are never treated as a full census of NYC businesses.

This tool identifies categories worth **testing**. It does not prove profitability. Unit costs, margins, fulfillment capacity, licensing, and actual conversion data still determine whether a category is commercially viable.

## Architecture

The application is isolated under `cookbook/nyc_product_category_discovery` and does not modify LiteLLM core.

```text
market_intel/
  models.py          strict Pydantic source, listing, demand, and output contracts
  sources.py         Overture, Google Ads, NYC Open Data, and licensed CSV collectors
  normalization.py   borough, category, numeric, boolean, and ID normalization
  analysis.py        deterministic evidence gate and opportunity scoring
  prompts.py         versioned prompts, router policy, and meta-prompt
  llm_client.py      provider-neutral structured calls through LiteLLM
  validation.py      cross-record evidence and deterministic-result validation
  workflow.py        research, classification, strategy, consensus, and copy stages
  evaluator.py       reproducible offline evaluation runner
  cli.py             command-line interface, logging, configuration, and errors
fixtures/
  eval_cases.json    exactly 20 evidence-policy cases
examples/
  business.json
  category_seeds.json
  competitors.csv
  competitors.csv.source.json
  demand.csv
  demand.csv.source.json
  coverage.csv
  coverage.csv.source.json
  taxonomy.json
```

### Model routing

The default configuration maps the requested workflow as follows:

| Responsibility | Default LiteLLM model |
|---|---|
| Current sourced research | `perplexity/sonar-pro` |
| Bulk listing classification | `deepseek/deepseek-v4-pro` |
| Preliminary analysis | `gemini/gemini-3.1-pro-preview` |
| Local direct-response copy | `anthropic/claude-sonnet-5` |
| Final synthesis | `openai/gpt-6-astra` |
| Material-decision review | Perplexity, DeepSeek, Gemini, and Claude independently |

The defaults were checked against current official model pages on September 14, 2026: [Perplexity Sonar Pro](https://docs.perplexity.ai/docs/sonar/models/sonar-pro), [DeepSeek API](https://api-docs.deepseek.com/), [Gemini models](https://ai.google.dev/gemini-api/docs/models), [Claude Sonnet 5](https://docs.anthropic.com/en/docs/about-claude/models/whats-new-sonnet-5), and [OpenAI models](https://platform.openai.com/docs/models). Sampling temperature is omitted by default because current Sonnet rejects non-default sampling parameters. Content was rephrased for compliance with licensing restrictions.

All identifiers are configurable in `config.example.json`. The router system prompt and preflight meta-prompt are exported as `ROUTER_SYSTEM_PROMPT` and `META_PROMPT` in `market_intel/prompts.py`.

The executable dependency order is deliberately stronger than the original numbered table:

```text
research -> collection -> normalization/classification -> deterministic analysis
         -> Gemini preliminary strategy -> GPT synthesis
         -> evidence-weighted consensus -> Claude copy
```

Classification occurs before analysis because analysis cannot safely compare unnormalized categories.

## Supported data sources

### Automated three-feed collection

`collect-market` produces the three datasets required by the decision engine:

1. **Competitors:** open Overture Maps place records inside official NYC borough boundaries.
2. **Demand:** borough-targeted keyword demand from Google Ads `KeywordPlanIdeaService`.
3. **Coverage:** one completed Overture category count for every candidate/borough pair, including zero-result searches.

Overture publishes its places theme under CDLA Permissive 2.0 or Apache 2.0 depending on source, releases it monthly, and documents known duplicate, junk, and completeness limitations: [Overture Places guide](https://docs.overturemaps.org/guides/places/). The official Python client streams bbox-filtered data from the latest release: [Overture Python client](https://docs.overturemaps.org/getting-data/overturemaps-py/). This implementation filters the bbox results through NYC Open Data's official [Borough Boundaries](https://data.cityofnewyork.us/City-Government/Borough-Boundaries/gthc-hcne) polygons before assigning Bronx or Queens.

Google Ads Keyword Planner can generate geographically targeted keyword ideas and historical search-volume metrics: [Generate keyword ideas](https://developers.google.com/google-ads/api/docs/keyword-planning/generate-keyword-ideas). API access requires OAuth credentials, a developer token, and a customer account: [Google Ads authentication](https://developers.google.com/google-ads/api/rest/auth). The application resolves borough geo targets through `GeoTargetConstantService`, runs one category request per borough, deduplicates returned keywords inside that request, and stores the summed average monthly searches as the category demand observation. The source limitation records that intent can overlap across categories. Overture places matching multiple mapped business categories count once in every matched category; duplicated taxonomy labels across category seeds are rejected.

### Additional persisted sources

- **NYC Open Data DCWP Issued Licenses:** optional active-license supply records for regulated categories.
- **Demand CSV:** Google Ads exports or first-party leads, orders, revenue, service requests, or survey observations.
- **Competitor CSV:** business data the operator is licensed or permitted to retain.
- **Coverage CSV:** proof that each borough/category supply query completed, including zero-result queries.

The DCWP collector uses NYC Open Data's official `w7w3-xahh` [Issued Licenses dataset](https://data.cityofnewyork.us/Business/Issued-Licenses/w7w3-xahh). It pins requests to the official HTTPS host so the optional Socrata token cannot be redirected to an operator-configured endpoint. DCWP coverage is limited to regulated categories and is not a census of every NYC business.

Google Places retrieval is intentionally not persisted. Google's policy limits caching and storage of Places content, while place IDs receive a specific exception: [Places API policies](https://developers.google.com/maps/documentation/places/web-service/policies). If Places is added later, it must use compliant ephemeral handling and attribution. Text Search also requires an explicit field mask: [Text Search documentation](https://developers.google.com/maps/documentation/places/web-service/text-search).

Every source records its license/terms label, attribution, retention permission, and whether raw records may be disclosed to model providers. Prompts receive a minimized packet; raw rows are withheld unless `provider_sharing_allowed` is true.

Content from these official sources was rephrased for compliance with licensing restrictions.

## Input contracts

### `category_seeds.json`

The automated collector requires an explicit bridge between a business category, its Google Ads seed keywords, and Overture taxonomy labels:

```json
{
  "Gift Baskets": {
    "keywords": ["gift basket delivery", "same day gift baskets"],
    "overture_categories": ["gift_shop"]
  }
}
```

Each array must be non-empty. Category seeds are hypotheses, not findings. Use Perplexity research to propose candidates, verify Overture labels against the current taxonomy, then run collection. `examples/category_seeds.json` contains a five-category demonstration plan; it does not assert that those categories are underserved.

### `competitors.csv`

Required columns: `competitor_name`, `borough`, `primary_category`.

Supported columns:

```text
competitor_name,borough,neighborhood,primary_category,secondary_categories,
price_min,price_max,rating,review_count,pickup,delivery,delivery_fee,
delivery_radius_miles,main_offer,ad_message,source_url,observed_at,external_id
```

Separate secondary categories with `|`. Valid boroughs normalize to Bronx, Queens, Manhattan, Brooklyn, or Staten Island. Unknown boroughs fail validation.

### `demand.csv`

```text
category,borough,metric,value,period_start,period_end,confidence
```

Allowed metrics are `monthly_searches`, `qualified_leads`, `orders`, `revenue_usd`, `service_requests`, and `survey_intent`. Do not mix different metrics for one category/borough observation. `confidence` ranges from 0 to 1.

### `coverage.csv`

```text
category,borough,query_completed,result_count,observed_at,query
```

`query_completed=true,result_count=0` is valid evidence. `query_completed=false` is insufficient data, regardless of the partial count.

### CSV provenance sidecar

For `/path/to/demand.csv`, create `/path/to/demand.csv.source.json`:

```json
{
  "content_hash": "<64-character lowercase SHA-256>",
  "evidence_use": "production",
  "decision_eligible": true,
  "license_name": "Internal first-party data",
  "attribution": "Business analytics export",
  "retention_allowed": true,
  "provider_sharing_allowed": false,
  "notes": "Describe collection method, scope, and known limitations."
}
```

Generate the hash locally with `python -c "import hashlib,sys; print(hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest())" /path/to/demand.csv`. Repeat for competitor and coverage CSVs. Setting provider sharing to false keeps raw rows out of model prompts; deterministic aggregates remain usable.

### Business profile

`examples/business.json` describes operating constraints. Replace the undecided product label and fill margin, cost, delivery-radius, exclusions, prohibited-claim fields, and `approved_copy_facts` when they become known. Each approved copy fact has a stable `fact_id`, exact approved text, and optional category/borough scope. Claude copy is suppressed when no matching approved facts exist and remains marked `draft_requires_human_review`. Missing commercial constraints remain null; they are not inferred.

The CSV files under `examples/` use synthetic `example.test` records solely to exercise the pipeline. Their hash-bound `.source.json` files mark them `synthetic` and `decision_eligible=false`, so deterministic analysis returns `insufficient_data`. They are not market evidence and cannot be promoted merely by moving or renaming them.

Every CSV used for a production decision needs an adjacent `<filename>.source.json` provenance file. The sidecar must contain the CSV's SHA-256 `content_hash`, `evidence_use="production"`, `decision_eligible=true`, license/attribution fields, retention permission, provider-sharing permission, and notes describing origin and scope. A missing sidecar leaves the file verified for integrity but `unknown` and ineligible; a hash mismatch fails import. This separates successful file reading from permission to use its contents as market evidence.

## Running the workflow

Use Python 3.10 or newer from the repository environment. Install the cookbook's collection dependencies, then expose the local package:

```bash
python -m pip install -r cookbook/nyc_product_category_discovery/requirements.txt
export PYTHONPATH="cookbook/nyc_product_category_discovery"
```

For the automated Google Ads demand pull, configure credentials through environment variables or the Google Ads client configuration supported by the official library:

```bash
export GOOGLE_ADS_DEVELOPER_TOKEN="..."
export GOOGLE_ADS_CLIENT_ID="..."
export GOOGLE_ADS_CLIENT_SECRET="..."
export GOOGLE_ADS_REFRESH_TOKEN="..."
export GOOGLE_ADS_CUSTOMER_ID="0000000000"
# Required only when access is through a manager account:
export GOOGLE_ADS_LOGIN_CUSTOMER_ID="0000000000"
```

Keep credentials outside repository files. The application removes hyphens from `GOOGLE_ADS_CUSTOMER_ID` and never writes credential values into artifacts.

### 1. Validate the evidence policy

```bash
python -m market_intel evaluate \
  --output cookbook/nyc_product_category_discovery/artifacts/eval-report.json
```

The command exits nonzero if any case fails. The suite must contain exactly 20 unique cases.

### 2. Pull competitors, demand, and coverage

```bash
python -m market_intel --config cookbook/nyc_product_category_discovery/config.example.json \
  collect-market \
  --business cookbook/nyc_product_category_discovery/examples/business.json \
  --categories cookbook/nyc_product_category_discovery/examples/category_seeds.json \
  --output-dir cookbook/nyc_product_category_discovery/data/market-run
```

This command runs the Overture and Google Ads collectors concurrently and writes:

- `competitors.jsonl`
- `demand.jsonl`
- `coverage.jsonl`
- `sources.json`
- `collection-plan.json`
- `evidence-packet.json`
- `manifest.json`

The evidence packet is immediately usable by `analyze` or `strategy`. A failed collector fails the run; the system does not silently substitute synthetic or model-generated data.

### 3. Pull optional regulated-business supply data

```bash
python -m market_intel --config cookbook/nyc_product_category_discovery/config.example.json \
  collect-dcwp \
  --output-dir cookbook/nyc_product_category_discovery/data/dcwp
```

`SOCRATA_APP_TOKEN` is optional but recommended for sustained use. Output includes normalized competitors, category coverage, the source record, and a limitation manifest.

### 4. Build an evidence packet

```bash
python -m market_intel --config cookbook/nyc_product_category_discovery/config.example.json \
  build-packet \
  --business cookbook/nyc_product_category_discovery/examples/business.json \
  --competitor-csv /path/to/competitors.csv \
  --demand-csv /path/to/demand.csv \
  --coverage-csv /path/to/coverage.csv \
  --output cookbook/nyc_product_category_discovery/artifacts/evidence-packet.json
```

Add `--include-dcwp` to fetch DCWP data directly while building, or add
`--dcwp-dir cookbook/nyc_product_category_discovery/data/dcwp` to reuse the output
from `collect-dcwp` without another network request. Do not use DCWP categories as
if they represented unlicensed businesses.

### 5. Run deterministic analysis

```bash
python -m market_intel --config cookbook/nyc_product_category_discovery/config.example.json \
  analyze \
  --packet cookbook/nyc_product_category_discovery/artifacts/evidence-packet.json \
  --output cookbook/nyc_product_category_discovery/artifacts/analysis.json
```

This stage requires no model credentials. It is the authoritative category ranking and borough gate.

### 6. Run sourced candidate research

```bash
python -m market_intel --config cookbook/nyc_product_category_discovery/config.example.json \
  research \
  --business cookbook/nyc_product_category_discovery/examples/business.json \
  --question "Which pickup-and-delivery categories show current demand in the Bronx and Queens?" \
  --output cookbook/nyc_product_category_discovery/artifacts/research.json
```

The research stage verifies returned public HTTP(S) URLs and downgrades inaccessible sources. It rejects local/private addresses and model-returned file URLs, pins each validated public IP for the connection to prevent DNS rebinding, and removes candidates whose cited sources fail verification. Research candidates are hypotheses until converted into demand and completed supply observations.

### 7. Bulk classify listings

```bash
python -m market_intel --config cookbook/nyc_product_category_discovery/config.example.json \
  classify \
  --packet cookbook/nyc_product_category_discovery/artifacts/evidence-packet.json \
  --taxonomy cookbook/nyc_product_category_discovery/examples/taxonomy.json \
  --batch-size 50 \
  --updated-packet cookbook/nyc_product_category_discovery/artifacts/classified-packet.json \
  --output cookbook/nyc_product_category_discovery/artifacts/classifications.json
```

Every provider-shareable input record must be classified or explicitly returned as unclassified. Primary and secondary categories outside the supplied taxonomy are rejected. `--updated-packet` applies validated classifications instead of leaving them as a detached artifact. Raw records whose source forbids model-provider sharing are not sent for classification.

### 8. Run strategy or the full chain

```bash
python -m market_intel --config cookbook/nyc_product_category_discovery/config.example.json \
  strategy \
  --packet cookbook/nyc_product_category_discovery/artifacts/evidence-packet.json \
  --full \
  --output cookbook/nyc_product_category_discovery/artifacts/final-result.json
```

Without `--full`, the command runs deterministic analysis, Gemini preliminary strategy, and GPT synthesis. A successful strategy run is labeled `supported_with_unvalidated_proposals`: deterministic rankings are supported, while every model-written angle, practice, and action remains explicitly unvalidated. With `--full`, it also runs independent evidence-weighted consensus and generates a Claude copy draft only when the category decision and borough priority are supported for the same category/borough cell and matching operator-approved copy facts exist. Consensus receives immutable deterministic aggregates, including demand values and observation IDs, while raw Google Ads rows remain withheld. A tied consensus, unsupported borough, or missing approved copy facts changes the final run status to `insufficient_data`; no arbitrary fallback category is advertised. Strategy claims declare a demand, supply, competitor, or combined evidence type; competitor practices include exact JSON-encoded source-field values and matching category/borough records. Expected action impact remains `unknown until measured`. Copy reproduces cited approved facts exactly, blocks unapproved promotional claims, and is always labeled `draft_requires_human_review`.

Set provider keys according to the selected LiteLLM models. To route through an existing gateway instead, set `LITELLM_PROXY_URL` and `LITELLM_PROXY_API_KEY`. Credentials are read from the environment and excluded from public configuration snapshots.

## Opportunity score

The default deterministic score is:

```text
55% normalized category demand + 45% inverse normalized supply
```

Normalization occurs once across the comparable Bronx/Queens category-and-borough cells, never independently per borough. A single category cannot establish a relative market gap under the default minimum of two. Every compared category must use one positive demand observation with the same metric and exact period, plus one fresh completed supply count. Cross-borough ranking is suppressed when primary boroughs use different metrics or periods, and borough priority additionally requires the same supported category set. Future-dated, duplicated, overlapping, low-confidence, failed-source, non-production, or mixed-unit observations are insufficient until normalized. Competitor weakness and business fit default to zero weight because those components require additional evidence. If their weights are enabled, missing component data makes the category insufficient rather than assigning a neutral estimate.

Borough priority compares the mean score of each borough's five strongest supported categories. Both primary boroughs must have support. Exact ties return `insufficient_data`.

## Production sequence

1. Run Perplexity research to establish a broad candidate hypothesis list.
2. Review candidates for operational feasibility and map each to verified Overture taxonomy labels and Google Ads keywords in `category_seeds.json`.
3. Run `collect-market` to pull Overture competitors, completed category coverage, and Google Ads demand into one timestamped packet.
4. Run deterministic analysis. Any missing, mismatched, stale, or duplicated evidence remains `insufficient_data`.
5. Use model synthesis and independent consensus only after deterministic support exists.
6. Validate the leading category with a small controlled campaign.
7. Feed qualified leads, orders, revenue, fulfillment cost, and margin back as first-party observations.

That measured feedback loop—not model voting—is what improves the decision over time. No real category recommendation exists in this repository yet because Google Ads credentials have not been configured and no full Bronx/Queens market collection has been run. The included examples and evaluation fixtures are synthetic.
