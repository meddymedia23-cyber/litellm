export const PACKAGES = Object.freeze([
  Object.freeze({
    id: "orbit-035",
    size: "3.5g",
    sequence: "01",
    name: "Orbit Mini",
    artwork: "Orbital lines",
    description: "A compact empty-pouch concept with a high-energy orbital graphic system.",
    palette: Object.freeze(["#10152f", "#52f7d4", "#ff4d8d"]),
    visual: Object.freeze({ width: 1.55, height: 2.05, depth: 0.18, corner: 0.16, pattern: 0 }),
  }),
  Object.freeze({
    id: "signal-070",
    size: "7g",
    sequence: "02",
    name: "Signal Shift",
    artwork: "Signal grid",
    description: "An empty-pouch concept built around signal lines, scan fields, and luminous contrast.",
    palette: Object.freeze(["#171126", "#8d6bff", "#ffca5c"]),
    visual: Object.freeze({ width: 1.78, height: 2.48, depth: 0.21, corner: 0.18, pattern: 1 }),
  }),
  Object.freeze({
    id: "phase-140",
    size: "14g",
    sequence: "03",
    name: "Phase Bloom",
    artwork: "Layered bloom",
    description: "A medium empty-pouch concept with layered petals and shifting color fields.",
    palette: Object.freeze(["#23101b", "#ff6c54", "#b7ff5a"]),
    visual: Object.freeze({ width: 2.02, height: 2.88, depth: 0.24, corner: 0.2, pattern: 2 }),
  }),
  Object.freeze({
    id: "vector-280",
    size: "28g",
    sequence: "04",
    name: "Vector Field",
    artwork: "Vector rays",
    description: "A large empty-pouch concept composed from directional geometry and deep color.",
    palette: Object.freeze(["#071f28", "#4edbff", "#ff5e6f"]),
    visual: Object.freeze({ width: 2.28, height: 3.26, depth: 0.28, corner: 0.22, pattern: 3 }),
  }),
  Object.freeze({
    id: "monolith-1lb",
    size: "1lb",
    sequence: "05",
    name: "Monolith One",
    artwork: "Nested frames",
    description: "An oversized empty-pouch concept with monumental type and a restrained spectral surface.",
    palette: Object.freeze(["#0d0d10", "#e7ebf0", "#ff3b5f"]),
    visual: Object.freeze({ width: 3.05, height: 4.12, depth: 0.36, corner: 0.28, pattern: 4 }),
  }),
]);

export function getPackage(id) {
  return PACKAGES.find((item) => item.id === id) ?? PACKAGES[0];
}
