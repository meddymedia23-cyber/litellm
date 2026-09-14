---
inclusion: auto
---

# NYC Market Intelligence Project

## Goal

Build an evidence-based system that identifies product or service categories worth validating for a no-storefront NYC business using appointment pickup and delivery. Bronx and Queens are primary; Manhattan and Brooklyn are secondary.

## Decision standard

- Never invent market facts, competitor capabilities, demand, pricing, delivery, pickup, margins, or borough preference.
- Use the exact phrase `insufficient data` when the evidence gate fails.
- A category can be called underserved only when the same run contains fresh category-level demand and a fresh completed supply query for the same borough.
- Require comparable demand metric and observation periods across candidates.
- Require one deduplicated demand observation and one documented supply count per category/borough.
- Treat research-model candidates as hypotheses until quantitative demand and supply coverage are collected.
- Synthetic examples and evaluation fixtures are never market evidence.

## Implemented system

The implementation lives at `cookbook/nyc_product_category_discovery/` inside the LiteLLM fork.

- Overture Maps Places provides open competitor POIs and supply coverage; a place matching multiple mapped categories counts once in each category.
- NYC Open Data Borough Boundaries filters bbox results into actual Bronx and Queens polygons.
- Google Ads KeywordPlanIdeaService provides borough-targeted search-demand observations.
- NYC DCWP Issued Licenses is an optional regulated-business source and is not a complete business census.
- CSV imports require a hash-bound `.source.json` provenance sidecar to become decision eligible; synthetic and unknown files fail closed.
- Deterministic analysis uses observation-level evidence IDs and one shared normalization scope; incompatible cross-borough metrics or periods suppress ranking and borough priority.
- LiteLLM routes research, classification, analysis, copy, synthesis, and consensus stages.
- Deterministic analysis controls scores and borough priority; models cannot rewrite those findings.
- Raw source rows are disclosed to model providers only when source metadata permits provider sharing; consensus receives safe immutable aggregates instead of private Google Ads rows.
- Model-returned local file URLs and private network addresses fail research verification; each public DNS result is pinned for the connection to prevent rebinding, and candidates citing failed sources are removed.
- Strategy observations are field-level and exact; every angle, practice, and action remains an explicitly unvalidated proposal with unknown impact.
- Claude copy requires exact operator-approved facts, blocks unapproved promotional claims, and remains a human-review draft.
- The 20-case offline evidence suite passed 20/20 on September 14, 2026.
- A small live Overture adapter probe successfully found and normalized records, but it was not a full borough market run and must not be used as a category recommendation.

## Current data status

No defensible recommendation about what to sell exists yet. The repository contains synthetic demonstration categories only. A full run requires:

1. Google Ads OAuth credentials, developer token, customer ID, and optional manager account ID configured through environment variables.
2. A reviewed `category_seeds.json` mapping candidate categories to Google Ads keywords and current Overture taxonomy labels.
3. A complete `collect-market` run for Bronx and Queens.
4. Deterministic analysis of the resulting evidence packet.

## Model responsibilities

- Perplexity: sourced candidate research only.
- DeepSeek: high-volume taxonomy classification.
- Gemini: preliminary explanation of deterministic analysis.
- Claude: local direct-response ad copy after a supported decision.
- GPT: final strategy synthesis without changing deterministic findings.
- Perplexity, DeepSeek, Gemini, and Claude: independent consensus review for a material category decision.
- Hermes router prompt: enforce stage routing, schemas, retries, minimization, and fail-closed behavior.

## Feedback loop

After a controlled market test, retain prompt/model version, borough, category, spend, impressions, clicks, leads, orders, revenue, fulfillment cost, gross margin, acceptance decision, and rejection reason. Favor measured commercial outcomes over model confidence or majority voting.
