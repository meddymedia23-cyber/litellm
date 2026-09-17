import "./styles.css";
import { PACKAGES, getPackage } from "./catalog.js";
import { createStorefrontScene } from "./scene.js";

const app = document.querySelector("#app");

app.innerHTML = `
  <main class="site-shell">
    <header class="topbar">
      <a class="brand" href="#top" aria-label="Baggies Project home">
        <span class="brand-mark" aria-hidden="true"></span>
        <span>Baggies Project</span>
      </a>
      <div class="topbar-meta" aria-label="Collection summary">
        <span>Chromatic series</span>
        <span class="meta-divider" aria-hidden="true"></span>
        <span>Five original formats</span>
      </div>
    </header>

    <section class="hero" id="top" aria-labelledby="hero-title">
      <div class="hero-copy">
        <p class="eyebrow"><span>Edition 01—05</span> Chromatic pouch studies</p>
        <h1 id="hero-title">Color lives<br><em>in motion.</em></h1>
        <p class="hero-intro">Five empty-pouch concepts transformed into a luminous, orbitable street-tech collection.</p>
        <div class="hero-actions">
          <button class="action action-primary" type="button" data-action="explore">Explore the collection</button>
          <button class="action action-secondary" type="button" data-action="compare">Compare all sizes</button>
        </div>
      </div>

      <div class="scene-shell" aria-label="Interactive 3D pouch viewer">
        <div class="scene-glow" aria-hidden="true"></div>
        <div class="scene-mount" data-scene aria-hidden="true"></div>
        <div class="scene-status" data-scene-status role="status">Building the collection…</div>
        <div class="scene-fallback" data-scene-fallback hidden>
          <div class="fallback-pouch" aria-hidden="true"><span>3.5g</span></div>
          <p>3D preview unavailable. The full catalog remains accessible below.</p>
        </div>
        <div class="scene-badge" aria-hidden="true"><span>Original art</span><b data-active-sequence>01</b></div>
        <div class="scene-index" aria-hidden="true">
          <span>Chromatic</span><i></i><span>Series 01</span>
        </div>
        <p class="drag-cue" aria-hidden="true"><span></span> Drag to orbit · tap side bags</p>
      </div>

      <aside class="detail-panel" aria-live="polite">
        <div class="detail-sequence" data-detail-sequence>Study 01</div>
        <div class="detail-size" data-detail-size>3.5g</div>
        <h2 data-detail-name>Neon Orbit</h2>
        <p class="detail-tagline" data-detail-tagline></p>
        <p data-detail-description></p>
        <dl>
          <div><dt>Format</dt><dd data-detail-format></dd></div>
          <div><dt>Artwork</dt><dd data-detail-artwork></dd></div>
          <div><dt>Status</dt><dd>Concept only</dd></div>
        </dl>
        <p class="truth-note">Visual scale is illustrative. No price, inventory, availability, or store information is asserted.</p>
      </aside>
    </section>

    <section class="catalog" aria-labelledby="catalog-title">
      <div class="catalog-heading">
        <div>
          <p class="eyebrow">Select a format</p>
          <h2 id="catalog-title">Choose your signal</h2>
        </div>
        <p>Five exclusive color systems drawn in code. Select a card to bring its pouch into the center stage.</p>
      </div>
      <div class="size-grid" data-size-grid></div>
    </section>

    <footer class="footer">
      <p>Baggies Project <span>—</span> Empty packaging concepts</p>
      <p>Store details intentionally omitted</p>
    </footer>
  </main>
`;

const detail = {
  sequence: document.querySelector("[data-detail-sequence]"),
  size: document.querySelector("[data-detail-size]"),
  name: document.querySelector("[data-detail-name]"),
  tagline: document.querySelector("[data-detail-tagline]"),
  description: document.querySelector("[data-detail-description]"),
  format: document.querySelector("[data-detail-format]"),
  artwork: document.querySelector("[data-detail-artwork]"),
  activeSequence: document.querySelector("[data-active-sequence]"),
};

const sizeGrid = document.querySelector("[data-size-grid]");
let selectedId = PACKAGES[0].id;
let compareMode = false;
let sceneApi = null;

function renderCards() {
  sizeGrid.replaceChildren(
    ...PACKAGES.map((item) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "size-card";
      button.dataset.packageId = item.id;
      button.setAttribute("aria-pressed", String(item.id === selectedId && !compareMode));
      button.style.setProperty("--card-bg", item.palette[0]);
      button.style.setProperty("--card-a", item.palette[1]);
      button.style.setProperty("--card-b", item.palette[2]);
      button.style.setProperty("--card-c", item.palette[3]);

      const sequence = document.createElement("span");
      sequence.className = "card-sequence";
      sequence.textContent = `Edition ${item.sequence}`;

      const visual = document.createElement("span");
      visual.className = `card-visual card-pattern-${item.visual.pattern}`;
      visual.setAttribute("aria-hidden", "true");

      const pouch = document.createElement("span");
      pouch.className = "card-pouch";
      const pouchBrand = document.createElement("span");
      pouchBrand.className = "card-pouch-brand";
      pouchBrand.textContent = "BP";
      const pouchSize = document.createElement("span");
      pouchSize.className = "card-pouch-size";
      pouchSize.textContent = item.size;
      pouch.append(pouchBrand, pouchSize);
      visual.append(pouch);

      const copy = document.createElement("span");
      copy.className = "card-copy";
      const size = document.createElement("strong");
      size.textContent = item.size;
      const name = document.createElement("span");
      name.className = "card-name";
      name.textContent = item.name;
      const artwork = document.createElement("span");
      artwork.className = "card-artwork";
      artwork.textContent = item.artwork;
      copy.append(size, name, artwork);

      button.append(sequence, visual, copy);
      button.addEventListener("click", () => selectPackage(item.id));
      return button;
    }),
  );
}

function updateDetail(item) {
  detail.sequence.textContent = `Study ${item.sequence}`;
  detail.size.textContent = item.size;
  detail.name.textContent = item.name;
  detail.tagline.textContent = item.tagline;
  detail.description.textContent = item.description;
  detail.format.textContent = `${item.size} empty pouch`;
  detail.artwork.textContent = item.artwork;
  detail.activeSequence.textContent = item.sequence;
  document.documentElement.style.setProperty("--active-accent", item.palette[1]);
}

function updateCardSelection() {
  document.querySelectorAll(".size-card").forEach((card) => {
    card.setAttribute("aria-pressed", String(card.dataset.packageId === selectedId && !compareMode));
  });
}

function selectPackage(id, { fromScene = false } = {}) {
  const item = getPackage(id);
  selectedId = item.id;
  compareMode = false;
  updateDetail(item);
  updateCardSelection();
  document.querySelector('[data-action="compare"]').textContent = "Compare all sizes";
  document.querySelector('[data-action="compare"]').classList.remove("is-active");
  if (!fromScene) sceneApi?.showPackage(item.id);
}

function toggleCompare() {
  compareMode = !compareMode;
  const button = document.querySelector('[data-action="compare"]');
  button.textContent = compareMode ? "Return to selected size" : "Compare all sizes";
  button.classList.toggle("is-active", compareMode);
  updateCardSelection();
  if (compareMode) {
    sceneApi?.showComparison();
  } else {
    sceneApi?.showPackage(selectedId);
  }
}

renderCards();
updateDetail(PACKAGES[0]);

const sceneStatus = document.querySelector("[data-scene-status]");
const sceneFallback = document.querySelector("[data-scene-fallback]");

try {
  sceneApi = createStorefrontScene(document.querySelector("[data-scene]"), {
    packages: PACKAGES,
    onSelect: (id) => selectPackage(id, { fromScene: true }),
    onReady: () => {
      sceneStatus.classList.add("is-hidden");
    },
  });
} catch (error) {
  console.error("Unable to initialize the 3D storefront", error);
  sceneStatus.hidden = true;
  sceneFallback.hidden = false;
}

const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
document.querySelector('[data-action="explore"]').addEventListener("click", () => {
  document.querySelector(".catalog").scrollIntoView({
    behavior: reducedMotion.matches ? "auto" : "smooth",
    block: "start",
  });
});
document.querySelector('[data-action="compare"]').addEventListener("click", toggleCompare);

let sceneDisposed = false;
window.addEventListener("pagehide", (event) => {
  if (!event.persisted && !sceneDisposed) {
    sceneApi?.dispose();
    sceneDisposed = true;
  }
});
