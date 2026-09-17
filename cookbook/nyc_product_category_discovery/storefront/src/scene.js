import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";

function roundedRectShape(width, height, radius) {
  const x = -width / 2;
  const y = -height / 2;
  const shape = new THREE.Shape();
  shape.moveTo(x + radius, y);
  shape.lineTo(x + width - radius, y);
  shape.quadraticCurveTo(x + width, y, x + width, y + radius);
  shape.lineTo(x + width, y + height - radius);
  shape.quadraticCurveTo(x + width, y + height, x + width - radius, y + height);
  shape.lineTo(x + radius, y + height);
  shape.quadraticCurveTo(x, y + height, x, y + height - radius);
  shape.lineTo(x, y + radius);
  shape.quadraticCurveTo(x, y, x + radius, y);
  return shape;
}

function drawPattern(context, item, width, height) {
  const [background, primary, accent] = item.palette;
  const gradient = context.createLinearGradient(0, 0, width, height);
  gradient.addColorStop(0, background);
  gradient.addColorStop(0.24, `${primary}d9`);
  gradient.addColorStop(0.48, background);
  gradient.addColorStop(0.72, `${accent}c8`);
  gradient.addColorStop(1, background);
  context.fillStyle = gradient;
  context.fillRect(0, 0, width, height);

  const spectral = context.createLinearGradient(0, 0, width, 0);
  spectral.addColorStop(0, "rgba(63,255,216,.12)");
  spectral.addColorStop(0.24, "rgba(113,94,255,.2)");
  spectral.addColorStop(0.48, "rgba(255,52,125,.2)");
  spectral.addColorStop(0.72, "rgba(255,215,61,.16)");
  spectral.addColorStop(1, "rgba(60,233,255,.12)");
  context.save();
  context.translate(width / 2, height / 2);
  context.rotate(-0.36);
  for (let band = -height; band < height; band += 78) {
    context.globalAlpha = band % 156 === 0 ? 0.95 : 0.5;
    context.fillStyle = spectral;
    context.fillRect(-width, band, width * 2, 18);
  }
  context.restore();

  context.save();
  context.globalCompositeOperation = "screen";
  context.lineCap = "round";

  if (item.visual.pattern === 0) {
    for (let radius = 90; radius < 620; radius += 72) {
      context.strokeStyle = radius % 144 === 0 ? `${accent}aa` : `${primary}88`;
      context.lineWidth = 6;
      context.beginPath();
      context.arc(width * 0.5, height * 0.38, radius, -0.5, Math.PI * 1.55);
      context.stroke();
    }
  } else if (item.visual.pattern === 1) {
    context.translate(width / 2, height / 2);
    context.rotate(-0.28);
    for (let x = -width; x < width; x += 78) {
      context.fillStyle = x % 156 === 0 ? `${accent}77` : `${primary}66`;
      context.fillRect(x, -height, 20, height * 2);
    }
    for (let y = -height; y < height; y += 96) {
      context.strokeStyle = `${accent}55`;
      context.lineWidth = 3;
      context.beginPath();
      context.moveTo(-width, y);
      context.lineTo(width, y + 240);
      context.stroke();
    }
  } else if (item.visual.pattern === 2) {
    for (let ring = 0; ring < 13; ring += 1) {
      context.strokeStyle = ring % 2 ? `${primary}8c` : `${accent}70`;
      context.lineWidth = 9 - ring * 0.35;
      context.beginPath();
      const points = 90;
      for (let point = 0; point <= points; point += 1) {
        const angle = (point / points) * Math.PI * 2;
        const radius = 72 + ring * 36 + Math.sin(angle * 5 + ring) * 20;
        const px = width * 0.5 + Math.cos(angle) * radius;
        const py = height * 0.42 + Math.sin(angle) * radius;
        if (point === 0) context.moveTo(px, py);
        else context.lineTo(px, py);
      }
      context.closePath();
      context.stroke();
    }
  } else if (item.visual.pattern === 3) {
    context.translate(width * 0.5, height * 0.42);
    for (let angle = 0; angle < Math.PI * 2; angle += Math.PI / 12) {
      const length = 280 + Math.sin(angle * 7) * 90;
      const gradientLine = context.createLinearGradient(0, 0, Math.cos(angle) * length, Math.sin(angle) * length);
      gradientLine.addColorStop(0, `${primary}dd`);
      gradientLine.addColorStop(1, `${accent}11`);
      context.strokeStyle = gradientLine;
      context.lineWidth = 12;
      context.beginPath();
      context.moveTo(0, 0);
      context.lineTo(Math.cos(angle) * length, Math.sin(angle) * length);
      context.stroke();
    }
  } else {
    const glow = context.createRadialGradient(width * 0.52, height * 0.4, 10, width * 0.52, height * 0.4, 440);
    glow.addColorStop(0, `${accent}bb`);
    glow.addColorStop(0.35, `${primary}55`);
    glow.addColorStop(1, "transparent");
    context.fillStyle = glow;
    context.fillRect(0, 0, width, height);
    for (let i = 0; i < 8; i += 1) {
      context.strokeStyle = i % 2 ? `${accent}99` : `${primary}80`;
      context.lineWidth = 3;
      context.strokeRect(95 + i * 30, 125 + i * 38, width - 190 - i * 60, height - 250 - i * 76);
    }
  }
  context.restore();

  let seed = item.visual.pattern * 92821 + 4177;
  const random = () => {
    seed = (seed * 1664525 + 1013904223) >>> 0;
    return seed / 4294967296;
  };
  context.save();
  context.globalCompositeOperation = "screen";
  for (let dot = 0; dot < 95; dot += 1) {
    const x = random() * width;
    const y = 90 + random() * (height - 230);
    const radius = 1 + random() * 5;
    context.fillStyle = dot % 3 === 0 ? `${accent}8a` : dot % 3 === 1 ? `${primary}78` : "rgba(255,255,255,.34)";
    context.beginPath();
    context.arc(x, y, radius, 0, Math.PI * 2);
    context.fill();
  }
  context.restore();

  context.save();
  context.translate(width * 0.5, height * 0.38);
  context.rotate(-0.14);
  context.strokeStyle = `${item.palette[3]}b0`;
  context.lineWidth = 15;
  context.lineCap = "round";
  context.beginPath();
  for (let step = 0; step <= 16; step += 1) {
    const x = -270 + step * 34;
    const y = Math.sin(step * 1.5 + item.visual.pattern) * 24 + Math.cos(step * 0.55) * 18;
    if (step === 0) context.moveTo(x, y);
    else context.lineTo(x, y);
  }
  context.stroke();
  context.restore();

  const topFade = context.createLinearGradient(0, 0, 0, height * 0.24);
  topFade.addColorStop(0, "rgba(255,255,255,.2)");
  topFade.addColorStop(1, "rgba(255,255,255,0)");
  context.fillStyle = topFade;
  context.fillRect(0, 0, width, height * 0.24);

  context.textAlign = "center";
  context.fillStyle = "#f6f2e8";
  context.font = "700 32px Arial, sans-serif";
  context.letterSpacing = "10px";
  context.shadowColor = "rgba(0,0,0,.7)";
  context.shadowBlur = 18;
  context.fillText("BAGGIES PROJECT", width / 2, 86);
  context.shadowBlur = 0;

  context.save();
  const foilBand = context.createLinearGradient(0, 0, width, 0);
  foilBand.addColorStop(0, "#37f4cf");
  foilBand.addColorStop(0.28, "#fff2b7");
  foilBand.addColorStop(0.52, "#ff4c91");
  foilBand.addColorStop(0.76, "#8a6bff");
  foilBand.addColorStop(1, "#4de7ff");
  context.fillStyle = foilBand;
  context.fillRect(42, 108, width - 84, 9);
  context.restore();

  context.font = "900 136px Arial Black, Arial, sans-serif";
  context.letterSpacing = "-7px";
  context.lineWidth = 19;
  context.strokeStyle = `${background}e8`;
  context.strokeText(item.size.toUpperCase(), width / 2, height * 0.53);
  context.shadowColor = `${primary}9c`;
  context.shadowBlur = 28;
  context.fillText(item.size.toUpperCase(), width / 2, height * 0.53);
  context.shadowBlur = 0;

  context.font = "700 42px Arial, sans-serif";
  context.letterSpacing = "6px";
  context.lineWidth = 10;
  context.strokeStyle = `${background}d9`;
  context.strokeText(item.name.toUpperCase(), width / 2, height * 0.62);
  context.fillText(item.name.toUpperCase(), width / 2, height * 0.62);

  context.strokeStyle = "rgba(246,242,232,.8)";
  context.lineWidth = 2;
  context.strokeRect(54, 132, width - 108, height - 250);
  context.strokeStyle = `${item.palette[3]}b0`;
  context.strokeRect(66, 144, width - 132, height - 274);

  context.fillStyle = `${background}c9`;
  context.fillRect(76, height - 196, width - 152, 94);
  context.strokeStyle = "rgba(246,242,232,.78)";
  context.strokeRect(76, height - 196, width - 152, 94);
  context.font = "600 21px Arial, sans-serif";
  context.letterSpacing = "4px";
  context.fillStyle = "#f6f2e8";
  context.fillText("EMPTY POUCH / ORIGINAL ART", width / 2, height - 140);

  context.save();
  context.translate(32, height * 0.62);
  context.rotate(-Math.PI / 2);
  context.font = "700 16px Arial, sans-serif";
  context.letterSpacing = "5px";
  context.fillStyle = `${item.palette[3]}e6`;
  context.fillText(`CHROMATIC SERIES / ${item.sequence}`, 0, 0);
  context.restore();
}

function createLabelTexture(item, renderer) {
  const canvas = document.createElement("canvas");
  canvas.width = 1536;
  canvas.height = 2048;
  const context = canvas.getContext("2d");
  if (!context) throw new Error("Canvas 2D is unavailable");
  drawPattern(context, item, canvas.width, canvas.height);
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  texture.anisotropy = Math.min(16, renderer.capabilities.getMaxAnisotropy());
  texture.minFilter = THREE.LinearMipmapLinearFilter;
  texture.magFilter = THREE.LinearFilter;
  return texture;
}

function normalizedShapeGeometry(shape, width, height) {
  const geometry = new THREE.ShapeGeometry(shape, 48);
  const position = geometry.getAttribute("position");
  const uv = geometry.getAttribute("uv");
  for (let index = 0; index < position.count; index += 1) {
    uv.setXY(index, position.getX(index) / width + 0.5, position.getY(index) / height + 0.5);
  }
  uv.needsUpdate = true;
  return geometry;
}

function createPouch(item, renderer) {
  const { width, height, depth, corner } = item.visual;
  const pouch = new THREE.Group();
  pouch.userData.packageId = item.id;

  const silhouette = roundedRectShape(width, height, corner);
  const bodyGeometry = new THREE.ExtrudeGeometry(silhouette, {
    depth,
    bevelEnabled: true,
    bevelSegments: 5,
    steps: 1,
    bevelSize: Math.min(0.055, corner * 0.28),
    bevelThickness: 0.04,
    curveSegments: 48,
  });
  bodyGeometry.center();

  const bodyMaterial = new THREE.MeshPhysicalMaterial({
    color: new THREE.Color(item.palette[0]),
    metalness: 0.72,
    roughness: 0.28,
    clearcoat: 0.82,
    clearcoatRoughness: 0.2,
    iridescence: 0.72,
    iridescenceIOR: 1.35,
    side: THREE.DoubleSide,
  });
  const body = new THREE.Mesh(bodyGeometry, bodyMaterial);
  body.castShadow = true;
  body.receiveShadow = true;
  body.userData.packageId = item.id;
  pouch.add(body);

  const labelScale = 0.935;
  const labelShape = roundedRectShape(width * labelScale, height * 0.92, corner * 0.72);
  const labelGeometry = normalizedShapeGeometry(labelShape, width * labelScale, height * 0.92);
  const labelTexture = createLabelTexture(item, renderer);
  const labelMaterial = new THREE.MeshPhysicalMaterial({
    map: labelTexture,
    emissive: new THREE.Color(0xffffff),
    emissiveMap: labelTexture,
    emissiveIntensity: 0.36,
    metalness: item.visual.pattern === 3 ? 0.22 : 0.62,
    roughness: item.visual.pattern === 3 ? 0.58 : 0.28,
    clearcoat: 0.65,
    clearcoatRoughness: 0.24,
    iridescence: item.visual.pattern === 4 ? 0.9 : 0.48,
    polygonOffset: true,
    polygonOffsetFactor: -2,
  });
  const label = new THREE.Mesh(labelGeometry, labelMaterial);
  label.position.set(0, -height * 0.012, depth / 2 + 0.065);
  label.userData.packageId = item.id;
  pouch.add(label);

  const seamMaterial = new THREE.MeshStandardMaterial({
    color: 0xdde3e8,
    metalness: 0.85,
    roughness: 0.26,
  });
  const zipper = new THREE.Mesh(
    new THREE.BoxGeometry(width * 0.88, Math.max(0.035, height * 0.014), depth * 0.54),
    seamMaterial,
  );
  zipper.position.set(0, height * 0.38, depth * 0.13);
  zipper.castShadow = true;
  zipper.userData.packageId = item.id;
  pouch.add(zipper);

  const zipperShadow = zipper.clone();
  zipperShadow.material = new THREE.MeshStandardMaterial({
    color: 0x15151a,
    metalness: 0.45,
    roughness: 0.5,
  });
  zipperShadow.position.y -= Math.max(0.04, height * 0.022);
  zipperShadow.position.z -= 0.008;
  pouch.add(zipperShadow);

  const topCrimp = new THREE.Mesh(
    new THREE.BoxGeometry(width * 0.93, Math.max(0.055, height * 0.034), depth * 0.78),
    new THREE.MeshPhysicalMaterial({
      color: new THREE.Color(item.palette[1]),
      emissive: new THREE.Color(item.palette[1]),
      emissiveIntensity: 0.08,
      metalness: 0.92,
      roughness: 0.2,
      iridescence: 0.85,
    }),
  );
  topCrimp.position.set(0, height * 0.442, 0);
  topCrimp.castShadow = true;
  topCrimp.userData.packageId = item.id;
  pouch.add(topCrimp);

  const lowerSeam = new THREE.Mesh(
    new THREE.BoxGeometry(width * 0.9, Math.max(0.04, height * 0.018), depth * 0.72),
    seamMaterial.clone(),
  );
  lowerSeam.material.color.set(item.palette[0]);
  lowerSeam.position.set(0, -height * 0.455, 0);
  lowerSeam.userData.packageId = item.id;
  pouch.add(lowerSeam);

  const ring = new THREE.Mesh(
    new THREE.TorusGeometry(Math.max(0.045, width * 0.037), Math.max(0.011, width * 0.009), 12, 32),
    seamMaterial.clone(),
  );
  ring.position.set(0, height * 0.455, depth / 2 + 0.085);
  ring.userData.packageId = item.id;
  pouch.add(ring);

  const sideSealMaterial = new THREE.MeshPhysicalMaterial({
    color: new THREE.Color(item.palette[4]),
    metalness: 0.88,
    roughness: 0.24,
    transparent: true,
    opacity: 0.58,
  });
  for (const side of [-1, 1]) {
    const sideSeal = new THREE.Mesh(
      new THREE.BoxGeometry(Math.max(0.025, width * 0.018), height * 0.82, depth * 0.74),
      sideSealMaterial.clone(),
    );
    sideSeal.position.set(side * width * 0.475, -height * 0.02, 0);
    sideSeal.userData.packageId = item.id;
    pouch.add(sideSeal);

    const notch = new THREE.Mesh(
      new THREE.CircleGeometry(Math.max(0.027, width * 0.022), 24),
      new THREE.MeshBasicMaterial({ color: 0x05060a, side: THREE.DoubleSide }),
    );
    notch.position.set(side * width * 0.475, height * 0.335, depth / 2 + 0.084);
    notch.userData.packageId = item.id;
    pouch.add(notch);
  }
  sideSealMaterial.dispose();

  const gusset = new THREE.Mesh(
    new THREE.TorusGeometry(width * 0.32, Math.max(0.018, depth * 0.075), 10, 48, Math.PI),
    new THREE.MeshStandardMaterial({
      color: new THREE.Color(item.palette[2]),
      emissive: new THREE.Color(item.palette[2]),
      emissiveIntensity: 0.05,
      metalness: 0.78,
      roughness: 0.34,
    }),
  );
  gusset.rotation.z = Math.PI;
  gusset.position.set(0, -height * 0.445, depth / 2 + 0.045);
  gusset.userData.packageId = item.id;
  pouch.add(gusset);

  pouch.rotation.set(-0.025, -0.24, -0.018);
  return pouch;
}

function disposeObject(root) {
  const geometries = new Set();
  const materials = new Set();
  const textures = new Set();

  root.traverse((object) => {
    if (object.geometry) geometries.add(object.geometry);
    if (!object.material) return;
    const objectMaterials = Array.isArray(object.material) ? object.material : [object.material];
    for (const material of objectMaterials) {
      materials.add(material);
      for (const value of Object.values(material)) {
        if (value?.isTexture) textures.add(value);
      }
    }
  });

  textures.forEach((texture) => texture.dispose());
  materials.forEach((material) => material.dispose());
  geometries.forEach((geometry) => geometry.dispose());
}

function supportsWebGL() {
  const canvas = document.createElement("canvas");
  return Boolean(canvas.getContext("webgl2") || canvas.getContext("webgl"));
}

export function createStorefrontScene(container, { packages, onSelect, onReady }) {
  if (!supportsWebGL()) throw new Error("WebGL is unavailable");

  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const scene = new THREE.Scene();
  scene.fog = new THREE.FogExp2(0x08080b, 0.085);

  const camera = new THREE.PerspectiveCamera(34, 1, 0.1, 100);
  camera.position.set(0.25, 0.18, 7.2);

  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: "high-performance" });
  const maxRenderPixels = 7680 * 4320;
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.34;
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFShadowMap;
  container.append(renderer.domElement);

  const controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.dampingFactor = 0.065;
  controls.enablePan = false;
  controls.minDistance = 4;
  controls.maxDistance = 18;
  controls.minPolarAngle = Math.PI * 0.3;
  controls.maxPolarAngle = Math.PI * 0.68;
  controls.autoRotate = !reduceMotion;
  controls.autoRotateSpeed = 0.72;
  controls.target.set(0, 0, 0);

  scene.add(new THREE.HemisphereLight(0xb9d8ff, 0x12040b, 1.6));
  const key = new THREE.DirectionalLight(0xffffff, 4.2);
  key.position.set(4, 6, 5);
  key.castShadow = true;
  key.shadow.mapSize.set(1024, 1024);
  key.shadow.radius = 5;
  scene.add(key);

  const cyan = new THREE.PointLight(0x35f2c2, 25, 15, 2);
  cyan.position.set(-4.2, 1.1, 3.8);
  scene.add(cyan);
  const red = new THREE.PointLight(0xff2f68, 28, 14, 2);
  red.position.set(4.1, -1.1, 3.2);
  scene.add(red);
  const violet = new THREE.PointLight(0x8d5cff, 18, 12, 2);
  violet.position.set(0, 3.8, -2.4);
  scene.add(violet);

  const floorMaterial = new THREE.MeshPhysicalMaterial({
    color: 0x101014,
    metalness: 0.58,
    roughness: 0.3,
    transparent: true,
    opacity: 0.82,
  });
  const floor = new THREE.Mesh(new THREE.CircleGeometry(8.5, 96), floorMaterial);
  floor.rotation.x = -Math.PI / 2;
  floor.position.y = -2.25;
  floor.receiveShadow = true;
  scene.add(floor);

  const rings = new THREE.Group();
  for (let radius = 1.6; radius <= 7.2; radius += 0.8) {
    const points = [];
    for (let index = 0; index < 96; index += 1) {
      const angle = (index / 96) * Math.PI * 2;
      points.push(new THREE.Vector3(Math.cos(angle) * radius, -2.235, Math.sin(angle) * radius));
    }
    const geometry = new THREE.BufferGeometry().setFromPoints(points);
    const material = new THREE.LineBasicMaterial({ color: 0x34343d, transparent: true, opacity: 0.36 });
    rings.add(new THREE.LineLoop(geometry, material));
  }
  scene.add(rings);

  const portal = new THREE.Group();
  for (let index = 0; index < 4; index += 1) {
    const material = new THREE.MeshBasicMaterial({
      color: index % 2 ? 0xff2f68 : 0x35f2c2,
      transparent: true,
      opacity: 0.12 - index * 0.018,
    });
    const arc = new THREE.Mesh(new THREE.TorusGeometry(3.1 + index * 0.42, 0.012, 6, 128), material);
    arc.position.set(0, 0.1, -2.5 - index * 0.12);
    portal.add(arc);
  }
  scene.add(portal);

  const shardGeometry = new THREE.TetrahedronGeometry(0.045, 0);
  const shardMaterial = new THREE.MeshPhysicalMaterial({
    color: 0xffffff,
    metalness: 0.9,
    roughness: 0.2,
    iridescence: 1,
    transparent: true,
    opacity: 0.65,
  });
  const shards = new THREE.InstancedMesh(shardGeometry, shardMaterial, 48);
  const shardMatrix = new THREE.Matrix4();
  for (let index = 0; index < 48; index += 1) {
    const angle = index * 2.399963;
    const radius = 3.6 + (index % 9) * 0.34;
    shardMatrix.compose(
      new THREE.Vector3(Math.cos(angle) * radius, ((index * 17) % 70) / 10 - 3.2, Math.sin(angle) * radius - 1.8),
      new THREE.Quaternion().setFromEuler(new THREE.Euler(angle * 0.21, angle * 0.37, angle * 0.13)),
      new THREE.Vector3(1, 1 + (index % 4) * 0.7, 0.7),
    );
    shards.setMatrixAt(index, shardMatrix);
  }
  scene.add(shards);

  const starsGeometry = new THREE.BufferGeometry();
  const starPositions = [];
  for (let index = 0; index < 420; index += 1) {
    const angle = index * 2.399963;
    const radius = 4.5 + (index % 29) * 0.16;
    starPositions.push(Math.cos(angle) * radius, ((index * 37) % 100) / 11 - 4.2, Math.sin(angle) * radius - 3);
  }
  starsGeometry.setAttribute("position", new THREE.Float32BufferAttribute(starPositions, 3));
  const starsMaterial = new THREE.PointsMaterial({ color: 0xaeb7c4, size: 0.016, transparent: true, opacity: 0.55 });
  const stars = new THREE.Points(starsGeometry, starsMaterial);
  scene.add(stars);

  const display = new THREE.Group();
  scene.add(display);
  let visiblePouches = [];
  let animationFrame = 0;
  let comparison = false;

  function clearDisplay() {
    for (const pouch of visiblePouches) {
      display.remove(pouch);
      disposeObject(pouch);
    }
    visiblePouches = [];
  }

  function fitCamera(width, height, comparisonView = false) {
    const fov = THREE.MathUtils.degToRad(camera.fov);
    const verticalDistance = height / (2 * Math.tan(fov / 2));
    const horizontalDistance = width / (2 * Math.tan(fov / 2) * Math.max(camera.aspect, 0.55));
    const distance = Math.max(verticalDistance, horizontalDistance) * (comparisonView ? 1.5 : 1.38);
    controls.target.set(0, 0, 0);
    camera.position.set(distance * 0.07, distance * 0.04, Math.max(4.5, distance));
    controls.update();
  }

  function showPackage(id) {
    comparison = false;
    clearDisplay();
    const selectedIndex = Math.max(0, packages.findIndex((entry) => entry.id === id));
    const neighbors = [
      packages[(selectedIndex - 1 + packages.length) % packages.length],
      packages[selectedIndex],
      packages[(selectedIndex + 1) % packages.length],
    ];

    neighbors.forEach((item, index) => {
      const pouch = createPouch(item, renderer);
      const isActive = index === 1;
      if (isActive) {
        const activeScale = 3.15 / item.visual.height;
        pouch.scale.setScalar(activeScale);
        pouch.userData.baseY = -0.08;
        pouch.position.set(0, pouch.userData.baseY, 0.25);
        pouch.rotation.y = -0.15;
      } else {
        const side = index === 0 ? -1 : 1;
        const normalizedScale = 1.65 / item.visual.height;
        pouch.scale.setScalar(normalizedScale);
        pouch.userData.baseY = -0.76;
        pouch.position.set(side * 1.72, pouch.userData.baseY, -1.05);
        pouch.rotation.y = side * -0.5;
        pouch.rotation.z = side * 0.05;
      }
      display.add(pouch);
      visiblePouches.push(pouch);
    });

    fitCamera(4.75, 3.5);
  }

  function showComparison() {
    comparison = true;
    clearDisplay();
    const gap = 0.22;
    const scale = 0.68;
    const totalWidth = packages.reduce((sum, item) => sum + item.visual.width * scale, 0) + gap * (packages.length - 1);
    let cursor = -totalWidth / 2;
    for (const item of packages) {
      const pouch = createPouch(item, renderer);
      pouch.scale.setScalar(scale);
      pouch.position.x = cursor + (item.visual.width * scale) / 2;
      pouch.userData.baseY = -2.05 + (item.visual.height * scale) / 2;
      pouch.position.y = pouch.userData.baseY;
      pouch.rotation.y = -0.08;
      cursor += item.visual.width * scale + gap;
      display.add(pouch);
      visiblePouches.push(pouch);
    }
    fitCamera(totalWidth, Math.max(...packages.map((item) => item.visual.height * scale)), true);
  }

  const raycaster = new THREE.Raycaster();
  const pointer = new THREE.Vector2();
  let pointerDown = null;

  function updatePointer(event) {
    const rect = renderer.domElement.getBoundingClientRect();
    pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
    pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
  }

  function pick(event) {
    updatePointer(event);
    raycaster.setFromCamera(pointer, camera);
    const hit = raycaster.intersectObjects(visiblePouches, true)[0];
    return hit?.object?.userData?.packageId ?? null;
  }

  function handlePointerMove(event) {
    renderer.domElement.style.cursor = pick(event) ? "pointer" : "grab";
  }

  function handlePointerDown(event) {
    pointerDown = { x: event.clientX, y: event.clientY };
  }

  function handlePointerUp(event) {
    if (!pointerDown) return;
    const distance = Math.hypot(event.clientX - pointerDown.x, event.clientY - pointerDown.y);
    pointerDown = null;
    if (distance > 6) return;
    const packageId = pick(event);
    if (packageId) {
      showPackage(packageId);
      onSelect(packageId);
    }
  }

  renderer.domElement.addEventListener("pointermove", handlePointerMove);
  renderer.domElement.addEventListener("pointerdown", handlePointerDown);
  renderer.domElement.addEventListener("pointerup", handlePointerUp);

  const resizeObserver = new ResizeObserver(() => {
    const width = Math.max(container.clientWidth, 1);
    const height = Math.max(container.clientHeight, 1);
    const nativePixelRatio = Math.min(window.devicePixelRatio || 1, 2);
    const pixelBudgetRatio = Math.sqrt(maxRenderPixels / (width * height));
    const renderPixelRatio = Math.max(0.5, Math.min(nativePixelRatio, pixelBudgetRatio));
    camera.aspect = width / height;
    camera.updateProjectionMatrix();
    renderer.setPixelRatio(renderPixelRatio);
    renderer.setSize(width, height, false);
  });
  resizeObserver.observe(container);

  function animate() {
    const time = performance.now() * 0.001;
    if (!reduceMotion) {
      visiblePouches.forEach((pouch, index) => {
        const baseY = pouch.userData.baseY ?? 0;
        pouch.position.y = baseY + Math.sin(time * 0.85 + index * 0.8) * 0.035;
      });
      stars.rotation.y = time * 0.008;
      portal.rotation.z = Math.sin(time * 0.16) * 0.05;
      shards.rotation.y = time * 0.018;
      shards.rotation.z = Math.sin(time * 0.13) * 0.08;
    }
    controls.update();
    renderer.render(scene, camera);
    animationFrame = requestAnimationFrame(animate);
  }

  showPackage(packages[0].id);
  animate();
  requestAnimationFrame(onReady);

  return {
    showPackage,
    showComparison,
    dispose() {
      cancelAnimationFrame(animationFrame);
      resizeObserver.disconnect();
      renderer.domElement.removeEventListener("pointermove", handlePointerMove);
      renderer.domElement.removeEventListener("pointerdown", handlePointerDown);
      renderer.domElement.removeEventListener("pointerup", handlePointerUp);
      controls.dispose();
      clearDisplay();
      disposeObject(rings);
      disposeObject(portal);
      floor.geometry.dispose();
      floorMaterial.dispose();
      shardGeometry.dispose();
      shardMaterial.dispose();
      starsGeometry.dispose();
      starsMaterial.dispose();
      renderer.dispose();
      renderer.domElement.remove();
    },
  };
}
