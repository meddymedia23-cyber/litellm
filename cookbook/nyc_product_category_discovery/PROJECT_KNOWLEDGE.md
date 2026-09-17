# NYC Market Intelligence Project Knowledge

Last reviewed: September 14, 2026

This document is the durable decision log for the NYC product-category discovery project. It separates implemented behavior, verified observations, proposed extensions, rejected approaches, and unresolved work so that ideas are never mistaken for production capabilities or market evidence.

## Status vocabulary

- **Implemented:** present on the feature branch and covered by local validation.
- **Verified observation:** directly observed, with the verification scope stated.
- **Proposed:** reviewed design that is not implemented.
- **Blocked:** cannot be completed without an external dependency or decision.
- **Rejected:** deliberately excluded because it conflicts with evidence, licensing, security, or maintainability requirements.

Human-facing failure text uses `insufficient data`. Machine-readable status fields use `insufficient_data`.

## Business objective and constraints

The system identifies product or service categories worth validating for a no-storefront NYC business with appointment pickup and delivery. The Bronx and Queens are primary boroughs; Manhattan and Brooklyn are secondary.

The requested decision output is:

1. five underserved categories;
2. three positioning angles;
3. borough priority;
4. competitor practices to copy or avoid; and
5. three ranked next actions.

Outputs fail closed at field and stage boundaries: a supported category ranking may coexist with an unsupported borough priority, while synthesis, consensus, or copy is suppressed when its own prerequisites are missing. The system does not prove profitability. Product cost, gross margin, fulfillment capacity, delivery radius, licensing, conversion, and customer retention require separate evidence.

## Non-negotiable evidence contract

A category can be described as underserved only when one run contains fresh category-level demand and a fresh completed supply query for the same category and borough. Global ranking additionally requires:

- the same demand metric;
- the same exact observation period;
- verified, fresh, decision-eligible sources;
- one deduplicated demand observation per category and borough;
- completed supply coverage, including explicit zero-result queries;
- one shared normalization scope; and
- at least two comparable categories.

Borough priority requires both primary boroughs and the same supported category set. Exact ties fail closed. Synthetic examples, evaluation fixtures, model output, retrieved prose, and unknown-provenance files are never production market evidence.

## Implemented architecture

The application is isolated under `cookbook/nyc_product_category_discovery/`; LiteLLM core and proxy behavior are unchanged.

The production dependency order is:

```text
research -> collection -> normalization/classification -> deterministic analysis
         -> Gemini preliminary explanation -> GPT synthesis
         -> four-provider consensus -> Claude copy
```

The CLI exposes these as separate operator-orchestrated stages. `strategy --full` starts from an existing evidence packet and runs deterministic analysis, synthesis, consensus, and conditional copy; it does not perform research, collection, or classification. Classification precedes analysis because categories cannot be safely compared before normalization. Deterministic analysis is authoritative: models cannot change category records, evidence IDs, scores, limitations, or borough priority.

### Implemented sources

- Overture Maps Places: competitor POIs and completed supply coverage.
- NYC Borough Boundaries dataset `gthc-hcne`: exact polygon filtering.
- Google Ads `KeywordPlanIdeaService`: borough-targeted category demand.
- DCWP Issued Licenses dataset `w7w3-xahh`: optional regulated-business context, never a complete business census.
- Licensed CSV imports: parsed without a sidecar if structurally valid, but eligible for decisions only with a valid hash-bound provenance sidecar.

A single Overture place may count once in every mapped category it matches. Duplicate taxonomy labels across category seeds are rejected. Google Ads keyword ideas are deduplicated inside each category-and-borough request; overlapping intent across separate categories remains a recorded limitation.

### Source and sharing controls

Every source records license or terms, attribution, retention permission, provider-sharing permission, evidence use, and decision eligibility. CSV sidecars bind those declarations to exact SHA-256 content. A valid hash proves file integrity, not production eligibility.

Raw rows are disclosed to model providers only when `provider_sharing_allowed` is true. Consensus receives immutable deterministic aggregates instead of private Google Ads rows. Public research URLs reject local files, private hosts, and private network addresses; validated public IPs are pinned for each request to prevent DNS rebinding.

### Generated-output controls

- Research candidates are hypotheses, not findings.
- Strategy observations cite exact source fields and JSON-encoded observed values.
- Positioning angles, competitor practices, and next actions remain unvalidated proposals.
- Expected action impact is `unknown until measured`.
- Copy requires exact operator-approved facts and remains `draft_requires_human_review`.
- A tied consensus, unsupported borough, or missing approved copy fact returns `insufficient_data`.

### Implemented 3D concept storefront

`storefront/` is an isolated Vite and Three.js **Chromatic Street-Tech Gallery** for five empty-pouch labels: 3.5g, 7g, 14g, 28g, and 1lb. The supplied pouch photos informed its saturated foil, stand-up silhouette, and bold front-art direction, but no supplied image, logo, character, trade dress, texture, or 3D model was copied. Five original procedural label systems use spectral bands, deterministic spray fields, abstract motifs, and edition marks. The 3D scene adds zipper tracks, top crimps, side seals, notch accents, gussets, portal lighting, foil shards, a three-pouch clickable hero, and a proportion-preserving comparison view.

The site retains accessible native size buttons, keyboard focus, reduced-motion behavior, responsive desktop/mobile/high-density layouts, and readable WebGL/JavaScript fallbacks. Labels render from 1536×2048 canvases with mipmaps and hardware-capped anisotropy. Scene rendering uses an 8K pixel budget to retain native scene resolution at device-pixel ratio 1 without accidental supersampling beyond 7680×4320 pixels. Its static production output is one self-contained HTML file with no external runtime assets.

The storefront is intentionally evidence-safe: it contains no store/location details, price, inventory, availability, pickup, delivery, rating, review, scarcity, or verified physical-specification claim. Scene dimensions are visual parameters only. The five entries are concepts rather than Merchant products, and structured metadata uses `CreativeWork` entries without offers. The site is not connected to Google APIs, checkout, or the market-decision pipeline.

### Storefront validation record

During the redesign session, clean `npm run build` and `npm audit` runs passed with Vite 8.3.0, Three.js 0.186.0, and zero reported vulnerabilities. Browser checks rendered WebGL without console errors at 1440×900 desktop and 390×844 mobile viewports. They verified first-viewport composition, all five selectors, retained keyboard focus, 1lb selection, clickable side-pouch promotion to 7g, five-size comparison, no external runtime scripts/styles, and no horizontal overflow.

A 7680×4320 browser viewport produced a native-resolution 2752×2398 scene drawing buffer at device-pixel ratio 1—6,599,296 pixels, below the 33,177,600-pixel cap—with loading cleared and no overflow or console error. Identity-deduplicated Three.js cleanup prevents shared geometry, material, or texture references from being disposed twice. Final semantic review reported `APPROVED` with zero P0/P1/P2 findings. Screenshots remain session artifacts rather than product evidence.

## Model routing

Configured defaults at the last review were:

| Stage | Configured model |
|---|---|
| Sourced research | `perplexity/sonar-pro` |
| Bulk classification | `deepseek/deepseek-v4-pro` |
| Preliminary explanation | `gemini/gemini-3.1-pro-preview` |
| Copy draft | `anthropic/claude-sonnet-5` |
| Final synthesis | `openai/gpt-6-astra` |
| Consensus | Perplexity, DeepSeek, Gemini, and Claude independently |

These are configuration values, not permanent availability guarantees. Provider availability and accepted parameters must be rechecked before production runs. Temperature is omitted unless explicitly configured because provider sampling-parameter support differs.

## Deterministic scoring

The default score is:

```text
55% normalized demand + 45% inverse normalized supply
```

Normalization runs once across comparable Bronx and Queens cells. Competitor weakness and business fit have zero default weight because they require additional evidence. Enabling either weight without complete component evidence makes the category insufficient rather than assigning a neutral estimate.

## Validation record

The following development-session checks were reported against implementation commit `2176973a906455afc49931625f364906dba24796` on September 14, 2026. They are not independently reproducible from committed logs or GitHub check artifacts:

- Ruff format and check: 15 files reported passed.
- Python compilation: reported passed.
- Offline evidence policy: 20 of 20 cases reported passed and reran successfully during the documentation update.
- Focused contract tests: 9 of 9 reported passed and reran successfully during the documentation update.
- Repository `make lint`: reported passed after the sandbox runtime received its missing `libatomic` system library, and reran successfully during the documentation update.
- Focused measured coverage: 56% was reported; no coverage threshold or lint budget was changed.
- Semantic review: reported approved with zero P0/P1 blockers.
- Synthetic end-to-end analysis: reported zero supported categories, null borough priority, and `insufficient_data`.

The 56% figure is a development-session measurement, not a declared project threshold. The repository does not contain CI-produced validation artifacts for these claims; future validation should use immutable GitHub checks or a committed machine-readable manifest.

A small Overture probe returned normalized records during development. It was not a complete borough run, has no committed immutable run artifact, and is ineligible for a recommendation.

## Delivery record

Delivery observation recorded September 14, 2026, before this knowledge-document update:

- Branch: `litellm_nyc_market_intelligence`
- Validated implementation baseline: `2176973a906455afc49931625f364906dba24796`
- Draft PR: <https://github.com/meddymedia23-cyber/litellm/pull/1>
- PR base at observation: `main` at `858871dacba3932c8ebd9b0c023e74da63573fee`
- Fork PR state at observation: open, draft, clean, and mergeable.
- GitHub checks at observation: none reported on the fork.
- Greptile, Veria, and Bugbot at observation: unavailable; missing results are not passes.
- Upstream PR attempt: blocked by repository/provider authorization.
- Merge and deployment at observation: not completed.

This is a historical observation, not a self-referential current-head declaration. The PR URL is authoritative for commits made after the validated implementation baseline and for subsequent CI, review, merge, or deployment changes.

## Current market-data status

There is no defensible recommendation about what to sell. The repository contains synthetic demonstration data and no committed complete production evidence packet for Bronx and Queens. Repository inspection cannot prove whether credentials exist outside version control; it can only establish that no credential-backed full-run artifact is committed.

A production collection requires:

1. Google Ads authentication and an accessible customer account;
2. an approved developer token;
3. `GOOGLE_ADS_CUSTOMER_ID` and, when applicable, `GOOGLE_ADS_LOGIN_CUSTOMER_ID`;
4. reviewed category seeds with Google Ads keywords and current Overture labels;
5. a complete `collect-market` run for Bronx and Queens; and
6. deterministic analysis of that exact evidence packet.

## Proposed target architecture

Status: **Proposed; not implemented as an end-to-end system.**

```text
                         Operator strategy and approvals
                                      |
                                      v
                  Proposed orchestration and retrieval layer
              configured LLM + policy-filtered, citation-checked RAG
                                      |
        +-----------------------------+-----------------------------+
        |                             |                             |
        v                             v                             v
 Google Ads demand             Merchant/catalog context      External market context
 implemented collector         proposed integration          proposed, source-specific
        |                             |                             |
        +-----------------------------+-----------------------------+
                                      |
                                      v
                  Deterministic evidence and policy gates
                                      |
                                      v
                Human-reviewed experiments and operations
          ads, products, listings, reviews, pickup, and delivery
```

Only the existing Google Ads collector and deterministic market workflow are implemented. The central layer is an orchestrator, not the evidence authority: deterministic analysis and operator approval remain the decision gates. Merchant, Business Profile, RAG, SERP/trends sources, n8n, and Ads Scripts remain proposed until each has authentication, provenance, retention, provider-sharing, failure-mode, and evaluation contracts. Retrieved or operational data cannot satisfy borough demand or completed supply requirements unless a future versioned evidence rule explicitly authorizes that use.

`GPT-5.6 Sol` is a user-supplied conceptual label, not a verified model identifier or project default. Any implementation must use a configured provider model whose exact identifier and capabilities have been verified at deployment time.

## Google Merchant integration review

Status: **Proposed; not implemented.**

The supplied prototype used `googleapiclient.discovery.build("content", "v2.1")`, the Content API for Shopping. Google sunset that API on August 18, 2026 and directs integrations to the Merchant API. New work must use the [Merchant API](https://developers.google.com/merchant/api) and its [Content API migration guidance](https://developers.google.com/merchant/api/guides/compatibility/overview).

Merchant product and issue data can support catalog readiness after a category has been selected. It can answer operational questions such as which owned products exist and which feed items have issues. It does **not** establish:

- borough-level category demand;
- keyword search volume;
- competitor counts;
- completed local supply coverage; or
- an underserved category.

Merchant records must therefore be contextual or operational data unless a future versioned evidence rule, evaluator cases, and semantic review authorize a narrower decision use. They cannot replace Google Ads demand or Overture coverage.

A future implementation must define account ownership, authentication, selected Merchant resources, pagination, quota handling, refresh cadence, stable product IDs, normalization, deletion, source lineage, retention, provider sharing, and failure behavior. Credentials stay outside the repository. Service-account use does not remove Google Ads requirements such as a developer token and customer-account access. See the official [Google Ads service-account workflow](https://developers.google.com/google-ads/api/docs/oauth/service-accounts).

## RAG agent review

Status: **Proposed; not implemented.**

The supplied `rag_agent.py` demonstrates the intended retrieve-then-answer loop:

```text
documents -> sentence-aware chunks -> batched embeddings -> Chroma upsert
question -> query embedding -> nearest chunks -> grounded answer with citations
```

Useful improvements over the first draft include batching chunks from one document, using `upsert`, returning distances, optional distance filtering, and instructing generation to admit missing context.

The prototype is not production-ready and was not committed as executable application code. The following corrections are required before implementation.

### Configuration and routing

- Do not assume `gpt-5.6-sol` is a valid provider model ID. Verify and configure the exact deployed identifier.
- Route model and embedding calls through the project's LiteLLM client or explicitly document why direct provider access is required.
- Bind every collection to its embedding model, dimensions, distance metric, corpus version, and schema version.
- Keep the Chroma path configurable and outside tracked source; add any selected local persistence path to `.gitignore`.

### Input validation and chunking

- Replace `assert` with explicit runtime validation; assertions disappear under optimized Python.
- Validate document shape, non-empty text, unique stable IDs, metadata types, chunk size, overlap, query length, and `k`.
- The prototype's “no mid-word cuts” claim is not exact: oversized sentences and character overlap can still split words.
- Define a token-aware context budget. Character counts do not guarantee model-token limits.
- Prevent arbitrarily large final chunks rather than allowing an undocumented overflow.

### Idempotency and lifecycle

- Derive document and chunk IDs from canonical source IDs plus content hashes.
- `upsert` alone does not remove obsolete trailing chunks when a revised document becomes shorter; delete or tombstone the previous document version before replacement.
- Batch across documents where safe, retry transient embedding errors with bounded backoff, and record partial failures.
- Support refresh, invalidation, deletion, backup, and corpus rebuilds.

### Metadata and evidence policy

Each chunk needs scalar, validated metadata sufficient for policy filtering and citation:

- canonical source ID and URL;
- source content hash and document version;
- observed/published timestamp;
- borough and category scope where applicable;
- license and attribution;
- retention permission;
- provider-sharing permission;
- evidence use and decision eligibility;
- deletion state;
- embedding model and schema version; and
- parent document ID plus chunk index.

Retrieval must filter these fields before returning context. Similarity never upgrades contextual prose into demand or supply evidence.

### Retrieval quality

- Cap `k` against collection size and define empty-index behavior.
- Calibrate thresholds against the collection's actual distance metric; a generic L2 threshold is not portable.
- Add metadata filters, deduplication, diversity controls, reranking where measured useful, and deterministic tie ordering.
- Evaluate retrieval with a fixed question set, expected source IDs, recall/precision metrics, and groundedness checks before allowing it into model stages.

### Generation safety

- Treat retrieved text as untrusted data. Delimit it and explicitly prohibit following instructions found inside documents.
- Accept only validated user/assistant history roles; arbitrary system messages in `history` must not be allowed.
- Enforce context and output limits, request timeouts, bounded retries, and structured error reporting.
- Do not catch every exception and retry without `reasoning_effort`; that masks authentication, quota, network, and provider failures and can duplicate cost. Retry only a confirmed unsupported-parameter error.
- Validate every generated citation against the retrieved chunk IDs.
- Report only sources actually cited, not every retrieved source.
- Missing context must use the project's fail-closed contract: human text `insufficient data`, machine status `insufficient_data`.

### Demo-data warning

The sample Merchant attributes, image date, click uplift, and store-rating thresholds in the supplied script were not accompanied by verified source records. They must be treated as synthetic demonstration text, not facts, and must never enter a production evidence collection.

For embeddings behavior and dimensions, consult the official [OpenAI embeddings guide](https://platform.openai.com/docs/guides/embeddings) and [API reference](https://platform.openai.com/docs/api-reference/embeddings/create) when implementing. Provider documentation must be rechecked at implementation time.

Content from linked official documentation was paraphrased. No external source text is reproduced as project evidence.

## Hugging Face Transformers evaluation

Status: **Evaluated; no runtime dependency added.**

At the September 14, 2026 review, [`huggingface/transformers`](https://github.com/huggingface/transformers) was active under the Apache-2.0 license and its latest stable release was [v5.17.0](https://github.com/huggingface/transformers/releases/tag/v5.17.0). The library provides model definitions and local inference/training primitives across text, vision, audio, video, and multimodal tasks. Its [pipeline API](https://huggingface.co/docs/transformers/main/en/main_classes/pipelines) includes classification, zero-shot classification, feature extraction, generation, question answering, and image tasks.

Transformers does not provide Google Ads or Merchant collection, source provenance, evidence eligibility, vector-store lifecycle, live cited research, deterministic opportunity scoring, agent memory, or this project's orchestration and validation contracts. Installing it would not improve the current evidence engine by itself.

### Dependency decision

Do not add `transformers` to the current cookbook requirements. There is no implemented local-inference command, selected checkpoint, benchmark, image contract, RAG command, hardware target, or acceptance threshold. Adding the library now would also introduce model downloads, tensor-runtime and cache requirements, checkpoint-specific licenses, and CPU/GPU resource behavior without an executable caller.

If local inference becomes justified, prefer either:

1. an optional backend implementing the existing structured client boundary; or
2. a separately served, LiteLLM-compatible local endpoint, keeping heavyweight inference dependencies out of the collector process.

A direct adapter must preserve Pydantic output validation, bounded retries, timeouts, redacted errors, usage/latency metadata, event-loop isolation, and every downstream evidence check.

### Prioritized future uses

1. **Local fixed-taxonomy listing classification:** strongest candidate. A local text or zero-shot classifier could reduce external disclosure and classify records against the supplied taxonomy, but it must preserve record IDs, explicit abstention, secondary-label rules, evidence text, batch completeness, and existing validation.
2. **Local embeddings or reranking for proposed RAG:** useful only after the documented corpus, metadata, deletion, citation, and retrieval-evaluation contracts exist. Computing vectors locally does not change source evidence eligibility.
3. **Advisory product-image checks:** possible after Merchant product/image schemas exist. ML may flag category/image inconsistency or content classes, while deterministic code must handle dimensions, format, hashes, duplicates, and fetch status. Image-model output cannot prove Merchant approval, legal compliance, product quality, demand, or supply.
4. **Local drafting or explanation:** possible for strategy or copy only if outputs pass the same immutable-result and approved-fact validators. It remains downstream of deterministic analysis and human review.

Do not replace sourced research with a plain local checkpoint: pretrained model knowledge is not live evidence and has no inherent URL provenance. Do not count aliases or quantizations of one checkpoint as independent consensus reviewers.

### Adoption gates

Before enabling any Transformers backend:

- define the exact stage, model repository, task, and business acceptance criteria;
- pin a stable Transformers release plus immutable model and tokenizer revisions rather than tracking `main`;
- review the selected checkpoint's own model card, dataset disclosures, license, intended use, and restrictions—the library's Apache-2.0 license does not license every Hub model;
- keep unreviewed remote model code disabled; if custom remote code is unavoidable, review it and pin its immutable revision;
- define cache location, offline behavior, egress policy, telemetry policy, retention, deletion, and resource limits;
- benchmark a representative labeled dataset against the existing provider using per-category quality, abstention behavior, calibration, latency, memory, and cost;
- define minimum quality thresholds before seeing results and fail closed below them;
- distinguish approved in-process local handling from external provider sharing instead of silently bypassing `provider_sharing_allowed`;
- add an optional dependency group, configuration schema, health checks, structured adapter, fallback policy, and focused tests in the same implementation change; and
- record model, tokenizer, library, hardware, quantization, prompt, and benchmark versions for every production result.

This evaluation adds a future decision gate, not an implementation commitment. Recheck current releases and documentation before adoption.

Content from linked official documentation was paraphrased for compliance with licensing restrictions.

## Rejected approaches

- Modifying LiteLLM core or proxy for domain-specific market logic.
- Extending the existing `hermes_corp` sample with hard-coded routes and import-time SQLite behavior.
- Persisting Google Places content without a reviewed policy-compliant design.
- Treating DCWP licenses as a complete business census.
- Treating Merchant products, vector similarity, model consensus, or research prose as market evidence.
- Letting models rewrite deterministic findings.
- Promoting synthetic or unknown-provenance files because they parse successfully.
- Using broad exception handling to silently downgrade model parameters.
- Committing credentials, provider tokens, local vector databases, or private raw records.

## Feedback loop

After a controlled campaign, retain the exact prompt and model versions, evidence packet ID, borough, category, spend, impressions, clicks, leads, orders, revenue, fulfillment cost, gross margin, acceptance decision, and rejection reason.

If retrieval is introduced, also retain corpus version, embedding model, chunk schema, retrieval parameters, retrieved chunk IDs, citation validation result, and retrieval-evaluation metrics. If Merchant synchronization is introduced, retain Merchant account scope, sync version, resource timestamps, normalization version, and deletion state without storing secrets.

Measured commercial outcomes outrank model confidence, similarity, or majority voting.
