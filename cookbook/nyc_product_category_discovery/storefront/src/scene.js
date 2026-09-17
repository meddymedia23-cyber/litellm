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
  gradient.addColorStop(0.52, `${primary}cc`);
  gradient.addColorStop(1, background);
  context.fillStyle = gradient;
  context.fillRect(0, 0, width, height);

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

  const topFade = context.createLinearGradient(0, 0, 0, height * 0.24);
  topFade.addColorStop(0, "rgba(255,255,255,.2)");
  topFade.addColorStop(1, "rgba(255,255,255,0)");
  context.fillStyle = topFade;
  context.fillRect(0, 0, width, height * 0.24);

  context.textAlign = "center";
  context.fillStyle = "#f6f2e8";
  context.font = "700 32px Arial, sans-serif";
  context.letterSpacing = "10px";
  context.fillText("BAGGIES PROJECT", width / 2, 86);

  context.font = "900 136px Arial Black, Arial, sans-serif";
  context.letterSpacing = "-7px";
  context.fillText(item.size.toUpperCase(), width / 2, height * 0.53);

  context.font = "700 42px Arial, sans-serif";
  context.letterSpacing = "6px";
  context.fillText(item.name.toUpperCase(), width / 2, height * 0.62);

  context.strokeStyle = "rgba(246,242,232,.62)";
  context.lineWidth = 2;
  context.strokeRect(76, height - 196, width - 152, 94);
  context.font = "600 21px Arial, sans-serif";
  context.letterSpacing = "4px";
  context.fillText("EMPTY POUCH CONCEPT", width / 2, height - 140);
}

function createLabelTexture(item, renderer) {
  const canvas = document.createElement("canvas");
  canvas.width = 768;
  canvas.height = 1024;
  const context = canvas.getContext("2d");
  if (!context) throw new Error("Canvas 2D is unavailable");
  drawPattern(context, item, canvas.width, canvas.height);
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  texture.anisotropy = Math.min(8, renderer.capabilities.getMaxAnisotropy());
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

  const labelScale = 0.91;
  const labelShape = roundedRectShape(width * labelScale, height * 0.9, corner * 0.72);
  const labelGeometry = normalizedShapeGeometry(labelShape, width * labelScale, height * 0.9);
  const labelTexture = createLabelTexture(item, renderer);
  const labelMaterial = new THREE.MeshPhysicalMaterial({
    map: labelTexture,
    metalness: item.visual.pattern === 3 ? 0.22 : 0.62,
    roughness: item.visual.pattern === 3 ? 0.58 : 0.28,
    clearcoat: 0.65,
    clearcoatRoughness: 0.24,
    iridescence: item.visual.pattern === 4 ? 0.9 : 0.48,
    polygonOffset: true,
    polygonOffsetFactor: -2,
  });
  const label = new THREE.Mesh(labelGeometry, labelMaterial);
  label.position.set(0, -height * 0.015, depth / 2 + 0.065);
  label.userData.packageId = item.id;
  pouch.add(label);

  const seamMaterial = new THREE.MeshStandardMaterial({
    color: 0xdde3e8,
    metalness: 0.85,
    roughness: 0.26,
  });
  const zipper = new THREE.Mesh(
    new THREE.BoxGeometry(width * 0.88, Math.max(0.045, height * 0.022), depth * 0.54),
    seamMaterial,
  );
  zipper.position.set(0, height * 0.385, depth * 0.12);
  zipper.castShadow = true;
  zipper.userData.packageId = item.id;
  pouch.add(zipper);

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
  ring.position.set(0, height * 0.445, depth / 2 + 0.075);
  ring.userData.packageId = item.id;
  pouch.add(ring);

  pouch.rotation.set(-0.025, -0.24, -0.018);
  return pouch;
}

function disposeObject(root) {
  root.traverse((object) => {
    if (object.geometry) object.geometry.dispose();
    if (!object.material) return;
    const materials = Array.isArray(object.material) ? object.material : [object.material];
    for (const material of materials) {
      if (material.map) material.map.dispose();
      material.dispose();
    }
  });
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
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.18;
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFShadowMap;
  container.append(renderer.domElement);

  const controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.dampingFactor = 0.065;
  controls.enablePan = false;
  controls.minDistance = 4;
  controls.maxDistance = 11;
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

  const cyan = new THREE.PointLight(0x4eead5, 16, 14, 2);
  cyan.position.set(-3.8, 0.8, 3.5);
  scene.add(cyan);
  const red = new THREE.PointLight(0xff315c, 18, 13, 2);
  red.position.set(3.6, -1.3, 2.8);
  scene.add(red);

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
    const distance = Math.max(verticalDistance, horizontalDistance) * (comparisonView ? 1.14 : 1.38);
    controls.target.set(0, 0, 0);
    camera.position.set(distance * 0.07, distance * 0.04, Math.max(4.5, distance));
    controls.update();
  }

  function showPackage(id) {
    comparison = false;
    clearDisplay();
    const item = packages.find((entry) => entry.id === id) ?? packages[0];
    const pouch = createPouch(item, renderer);
    display.add(pouch);
    visiblePouches.push(pouch);
    fitCamera(item.visual.width, item.visual.height);
  }

  function showComparison() {
    comparison = true;
    clearDisplay();
    const gap = 0.34;
    const scale = 0.58;
    const totalWidth = packages.reduce((sum, item) => sum + item.visual.width * scale, 0) + gap * (packages.length - 1);
    let cursor = -totalWidth / 2;
    for (const item of packages) {
      const pouch = createPouch(item, renderer);
      pouch.scale.setScalar(scale);
      pouch.position.x = cursor + (item.visual.width * scale) / 2;
      pouch.position.y = -2.05 + (item.visual.height * scale) / 2;
      pouch.rotation.y = -0.12;
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
    if (packageId && comparison) {
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
    camera.aspect = width / height;
    camera.updateProjectionMatrix();
    renderer.setSize(width, height, false);
  });
  resizeObserver.observe(container);

  function animate() {
    const time = performance.now() * 0.001;
    if (!reduceMotion) {
      visiblePouches.forEach((pouch, index) => {
        const baseY = comparison ? -2.05 + (packages[index].visual.height * 0.58) / 2 : 0;
        pouch.position.y = baseY + Math.sin(time * 0.85 + index * 0.8) * 0.035;
      });
      stars.rotation.y = time * 0.008;
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
      floor.geometry.dispose();
      floorMaterial.dispose();
      starsGeometry.dispose();
      starsMaterial.dispose();
      renderer.dispose();
      renderer.domElement.remove();
    },
  };
}
