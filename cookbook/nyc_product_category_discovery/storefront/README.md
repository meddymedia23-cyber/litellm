# Baggies Project Storefront

An isolated Three.js concept storefront for empty pouches in five requested size labels: 3.5g, 7g, 14g, 28g, and 1lb.

## Scope

- Original procedural pouch geometry and label artwork
- Single-product and five-size comparison views
- Keyboard-accessible size controls and readable WebGL fallback
- No store, location, price, inventory, availability, delivery, rating, or product-content claims
- Visual scene dimensions are illustrative and are not packaging specifications

## Run

```bash
npm install
npm run dev
```

Build the static site with:

```bash
npm run build
```

The generated `dist/` directory is intentionally ignored by the repository. Its `index.html` contains the complete application bundle for straightforward static hosting. Publish that build file through the chosen static host rather than committing generated output.

## Merchandising data

`src/catalog.js` is the only catalog source. Keep factual commerce fields out until real, reviewed data is available. If Google Merchant or store information is added later, it must use the evidence and provenance rules in the parent NYC market-intelligence project.

## Artwork provenance

Every visible package, texture, pattern, and mark is generated in repository code. The supplied reference images informed only the general request for colorful flexible-pouch presentation; no third-party logo, character, wordmark, package layout, or texture is copied.
