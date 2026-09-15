---
inclusion: auto
---

# NYC Market Intelligence Project

## Goal

Build an evidence-based system that identifies product or service categories worth validating for a no-storefront NYC business using appointment pickup and delivery. Bronx and Queens are primary; Manhattan and Brooklyn are secondary.

## Decision standard

- Never invent market facts, competitor capabilities, demand, pricing, delivery, pickup, margins, or borough preference.
- Human-facing failures use `insufficient data`; machine-readable status fields use `insufficient_data`.
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
- The 20-case offline evidence suite passed 20/20 locally at commit `2176973a90` on September 14, 2026; this is a local validation record, not GitHub CI evidence.
- A small live Overture adapter probe found and normalized records during development, but no immutable probe artifact is committed. It was not a full borough market run and is ineligible for recommendations.

## Proposed Merchant and RAG extensions

These designs are reviewed but not implemented. The complete decision record is in `cookbook/nyc_product_category_discovery/PROJECT_KNOWLEDGE.md`.

- Content API for Shopping v2.1 is sunset; any catalog integration must use the Merchant API.
- Merchant products and issue statuses are operational catalog context, not borough demand, competitor counts, or completed local supply coverage.
- A future RAG layer may index policy-eligible documents for contextual assistance, but retrieval similarity cannot become market evidence or override deterministic analysis.
- RAG implementation requires hash-bound IDs, stale-chunk deletion, scalar policy metadata, model/corpus versioning, provider-sharing filters, prompt-injection defenses, citation validation, bounded retries, and retrieval evaluation.
- The supplied RAG demo's product claims are synthetic because no verified source records accompanied them.
- Exact provider model IDs must be verified before implementation; `gpt-5.6-sol` is not an approved project default.
- Hugging Face Transformers was evaluated as a future optional local backend. No dependency is justified until a concrete stage has a pinned checkpoint, separate model-license review, representative benchmark, resource budget, and full evidence-policy validation.

## Delivery status

Historical observation from September 14, 2026, before the knowledge-document update: validated implementation baseline `2176973a90` was the head of branch `litellm_nyc_market_intelligence`, and draft PR <https://github.com/meddymedia23-cyber/litellm/pull/1> was open on the fork. The fork reported no GitHub checks or automated reviews; absent Greptile, Veria, and Bugbot results were unavailable, not passes. The change was not merged or deployed. The PR URL is authoritative for later documentation commits and delivery-state changes.

## Current data status

No defensible recommendation about what to sell exists yet. The repository contains synthetic demonstration categories only and no committed complete production evidence packet for Bronx and Queens. Repository inspection cannot establish whether external credentials exist; it establishes only that no credential-backed full-run artifact is committed. A full run requires:

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

After a controlled market test, retain prompt/model version, borough, category, spend, impressions, clicks, leads, orders, revenue, fulfillment cost, gross margin, acceptance decision, and rejection reason. If RAG is introduced, also retain corpus, embedding, chunk-schema, retrieval-parameter, and cited-chunk versions. If Merchant synchronization is introduced, retain account scope, sync and normalization versions, resource timestamps, and deletion state without secrets. Favor measured commercial outcomes over model confidence, vector similarity, or majority voting.
