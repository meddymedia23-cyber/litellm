# Baggies Project Storefront

A premium **Chromatic Street-Tech Gallery** built with Three.js for five empty-pouch concepts: 3.5g, 7g, 14g, 28g, and 1lb. The supplied pouch photos informed the saturated foil, stand-up silhouette, and bold front-art direction; every visible design remains original and generated in repository code.

## Scope

- Original procedural pouch geometry and five distinct chromatic label systems
- Three-bag hero carousel with clickable neighboring designs
- Five-size comparison view with true relative scene scaling
- Spectral foil layers, zipper tracks, top crimps, side seals, notch accents, and gussets
- 1536×2048 procedural label textures with mipmaps and up to 16× anisotropic filtering
- Dynamic render budgeting that keeps the 3D scene at native CSS-pixel resolution on an 8K display at device-pixel ratio 1, while capping total drawing work at 7680×4320 pixels
- Keyboard-accessible visual catalog cards and readable WebGL fallback
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
