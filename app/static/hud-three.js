/* Esfera holográfica 3D (demo-nucleo-3d). Arrastre + giro solo. */
/* Solo se inicia DESPUÉS del login (boot): el login va siempre fluido. */
const useThree = !!(window.THREE);
let three = null;

function initThree() {
  if (three || !useThree) return;
  try {
  const isLite = (typeof narrow === 'function' ? narrow() : false) || navigator.maxTouchPoints > 0;
  const box = document.getElementById('hud');
  const CYAN = 0x00d4ff;
  const ICE  = 0x7af0ff;
  const DEEP = 0x1488c8;

  function size() {
    return {
      w: box.clientWidth || innerWidth,
      h: Math.max(1, box.clientHeight || innerHeight)
    };
  }
  const s0 = size();

  const renderer = new THREE.WebGLRenderer({ antialias: !isLite, alpha: false });
  renderer.setSize(s0.w, s0.h);
  renderer.setPixelRatio(isLite ? 1 : Math.min(devicePixelRatio || 1, 1.5));
  renderer.setClearColor(0x02060c, 1);
  box.appendChild(renderer.domElement);

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(42, s0.w / s0.h, 1, 2000);
  camera.position.set(0, 18, 260);

  let controls = null;
  if (THREE.OrbitControls) {
    controls = new THREE.OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.07;
    controls.enablePan = false;
    controls.autoRotate = true;
    controls.autoRotateSpeed = 1.1;
    controls.minDistance = 140;
    controls.maxDistance = 480;
    controls.target.set(0, 0, 0);
  }

  function glowTex() {
    const c = document.createElement('canvas'); c.width = c.height = 128;
    const g = c.getContext('2d');
    const gr = g.createRadialGradient(64, 64, 0, 64, 64, 64);
    gr.addColorStop(0, 'rgba(255,255,255,1)');
    gr.addColorStop(0.2, 'rgba(180,245,255,.85)');
    gr.addColorStop(0.55, 'rgba(0,212,255,.2)');
    gr.addColorStop(1, 'rgba(0,0,0,0)');
    g.fillStyle = gr; g.fillRect(0, 0, 128, 128);
    return new THREE.CanvasTexture(c);
  }
  const gtex = glowTex();

  function lineMat(color, opacity) {
    return new THREE.LineBasicMaterial({
      color, transparent: true, opacity,
      blending: THREE.AdditiveBlending, depthWrite: false
    });
  }
  function meshMat(color, opacity) {
    return new THREE.MeshBasicMaterial({
      color, transparent: true, opacity,
      blending: THREE.AdditiveBlending, depthWrite: false, side: THREE.DoubleSide
    });
  }

  const globe = new THREE.Group();
  scene.add(globe);
  const layerA = new THREE.Group();
  const layerB = new THREE.Group();
  const layerC = new THREE.Group();
  globe.add(layerA, layerB, layerC);

  function wireSphere(radius, wSeg, hSeg, color, opacity) {
    const geo = new THREE.SphereGeometry(radius, wSeg, hSeg);
    const wire = new THREE.LineSegments(new THREE.WireframeGeometry(geo), lineMat(color, opacity));
    geo.dispose();
    return wire;
  }

  layerA.add(wireSphere(36, isLite ? 12 : 18, isLite ? 8 : 12, ICE,  0.22));
  layerB.add(wireSphere(58, isLite ? 18 : 28, isLite ? 12 : 18, CYAN, 0.28));
  layerC.add(wireSphere(82, isLite ? 24 : 40, isLite ? 16 : 24, DEEP, 0.32));

  function torusRing(radius, tube, color, opacity, arc) {
    return new THREE.Mesh(
      new THREE.TorusGeometry(radius, tube, 8, isLite ? 48 : 96, arc == null ? Math.PI * 2 : arc),
      meshMat(color, opacity)
    );
  }

  const equator = torusRing(82.5, 0.55, CYAN, 0.85);
  equator.rotation.x = Math.PI / 2;
  layerC.add(equator);

  const mer1 = torusRing(82.5, 0.28, ICE, 0.55);
  layerB.add(mer1);
  const mer2 = torusRing(82.5, 0.28, CYAN, 0.45);
  mer2.rotation.y = Math.PI / 2;
  layerB.add(mer2);
  const mer3 = torusRing(82.5, 0.22, DEEP, 0.4);
  mer3.rotation.y = Math.PI / 3;
  mer3.rotation.x = 0.4;
  layerA.add(mer3);

  [-0.62, -0.32, 0.32, 0.62].forEach((lat, i) => {
    const y = lat * 82;
    const r = Math.sqrt(82 * 82 - y * y);
    const t = torusRing(r, i % 2 ? 0.18 : 0.32, i % 2 ? ICE : CYAN, 0.5);
    t.rotation.x = Math.PI / 2;
    t.position.y = y;
    layerC.add(t);
  });

  const rim = new THREE.Group();
  rim.add(torusRing(94, 0.9, CYAN, 0.7));
  rim.rotation.x = Math.PI / 2;
  const tickMat = meshMat(ICE, 0.8);
  const TICKS = isLite ? 36 : 72;
  for (let i = 0; i < TICKS; i++) {
    const a = (i / TICKS) * Math.PI * 2;
    const long = i % 6 === 0;
    const h = long ? 5.5 : 2.2;
    const tick = new THREE.Mesh(new THREE.BoxGeometry(0.35, h, 0.35), tickMat);
    tick.position.set(Math.cos(a) * 97.5, Math.sin(a) * 97.5, 0);
    tick.rotation.z = a + Math.PI / 2;
    rim.add(tick);
  }
  layerC.add(rim);

  if (!isLite) {
    const rim2 = rim.clone();
    rim2.rotation.set(0.7, 0.25, 0.4);
    rim2.scale.setScalar(0.72);
    layerB.add(rim2);
  }

  const arcs = new THREE.Group();
  layerA.add(arcs);
  const ARC_N = isLite ? 10 : 22;
  for (let i = 0; i < ARC_N; i++) {
    const r = 40 + (i % 7) * 7;
    const arcLen = 0.45 + (i % 5) * 0.35;
    const tube = 0.1 + (i % 3) * 0.12;
    const mesh = torusRing(r, tube, i % 2 ? ICE : CYAN, 0.55 + (i % 3) * 0.12, arcLen);
    mesh.rotation.set(
      (i * 0.7) % Math.PI,
      (i * 1.3) % (Math.PI * 2),
      (i * 0.4) % Math.PI
    );
    arcs.add(mesh);
  }

  const blocks = new THREE.Group();
  const blockMat = meshMat(CYAN, 0.7);
  const BLOCK_N = isLite ? 8 : 16;
  for (let i = 0; i < BLOCK_N; i++) {
    const a = (i / BLOCK_N) * Math.PI * 2;
    const b = new THREE.Mesh(new THREE.BoxGeometry(1.6, 0.7, 0.25), blockMat);
    b.position.set(Math.cos(a) * 58, Math.sin(a) * 58, 0);
    b.lookAt(0, 0, 0);
    blocks.add(b);
  }
  blocks.rotation.y = 0.6;
  layerB.add(blocks);

  const core = new THREE.Mesh(
    new THREE.IcosahedronGeometry(2.2, 1),
    new THREE.MeshBasicMaterial({ color: 0xd4fbff })
  );
  globe.add(core);

  const marca = new THREE.Group();
  globe.add(marca);

  const FONT_URL = '/static/fonts/helvetiker_bold.typeface.json';
  if (THREE.FontLoader && THREE.TextGeometry) {
    new THREE.FontLoader().load(FONT_URL, function (font) {
      const geo = new THREE.TextGeometry('JARVIS', {
        font: font,
        size: isLite ? 7 : 9,
        height: isLite ? 5 : 9,
        curveSegments: isLite ? 4 : 6,
        bevelEnabled: true,
        bevelThickness: isLite ? 0.35 : 0.55,
        bevelSize: isLite ? 0.22 : 0.38,
        bevelSegments: isLite ? 2 : 3
      });
      geo.center();
      const matFront = new THREE.MeshBasicMaterial({ color: 0xffffff });
      const matSide = new THREE.MeshBasicMaterial({ color: 0xd0d6dc });
      const mesh = new THREE.Mesh(geo, [matFront, matSide]);
      while (marca.children.length) marca.remove(marca.children[0]);
      marca.add(mesh);
      marca.userData.mats = [matFront, matSide];
      marca.userData.mat = matFront;
    });
  }

  const glow = new THREE.Sprite(new THREE.SpriteMaterial({
    map: gtex, color: CYAN, transparent: true, opacity: 0.22,
    blending: THREE.AdditiveBlending, depthWrite: false
  }));
  glow.scale.set(22, 22, 1);
  globe.add(glow);
  const glow2 = glow.clone();
  glow2.material = glow.material.clone();
  glow2.material.opacity = 0.18;
  glow2.scale.set(110, 110, 1);
  globe.add(glow2);

  const PN = isLite ? 160 : 420;
  const pPos = new Float32Array(PN * 3);
  for (let i = 0; i < PN; i++) {
    const r = 20 + Math.pow(Math.random(), 0.7) * 78;
    const th = Math.random() * Math.PI * 2;
    const ph = Math.acos(2 * Math.random() - 1);
    pPos[i*3]     = r * Math.sin(ph) * Math.cos(th);
    pPos[i*3 + 1] = r * Math.sin(ph) * Math.sin(th);
    pPos[i*3 + 2] = r * Math.cos(ph);
  }
  const pGeo = new THREE.BufferGeometry();
  pGeo.setAttribute('position', new THREE.BufferAttribute(pPos, 3));
  const sparks = new THREE.Points(pGeo, new THREE.PointsMaterial({
    size: 1.8, map: gtex, color: ICE, transparent: true, opacity: 0.85,
    depthWrite: false, blending: THREE.AdditiveBlending
  }));
  globe.add(sparks);

  let composer = null;
  let bloomPass = null;
  if (!isLite && THREE.EffectComposer && THREE.UnrealBloomPass) {
    composer = new THREE.EffectComposer(renderer);
    composer.addPass(new THREE.RenderPass(scene, camera));
    bloomPass = new THREE.UnrealBloomPass(new THREE.Vector2(s0.w, s0.h), 0.55, 0.4, 0.32);
    composer.addPass(bloomPass);
  }

  const colorNow = new THREE.Color(CYAN);
  const colorTo  = new THREE.Color(CYAN);

  const onResize = () => {
    const s = size();
    camera.aspect = s.w / s.h;
    camera.updateProjectionMatrix();
    renderer.setSize(s.w, s.h);
    if (composer) composer.setSize(s.w, s.h);
  };
  addEventListener('resize', onResize);

  function paint(obj, color) {
    if (obj === core || obj === marca) return;
    if (obj.material && obj.material.color && obj !== core) obj.material.color.copy(color);
    for (let i = 0; i < obj.children.length; i++) paint(obj.children[i], color);
  }

  function tick(t) {
    three.rafId = requestAnimationFrame(tick);
    const speakingNow = typeof speaking !== 'undefined' && speaking;
    const thinking = document.getElementById('hud-ui') && document.getElementById('hud-ui').classList.contains('thinking');
    const spin = speakingNow ? 2.4 : thinking ? 1.7 : 1;

    if (controls) {
      controls.autoRotateSpeed = 0.9 * spin;
      controls.update();
    } else {
      globe.rotation.y += 0.004 * spin;
    }

    layerA.rotation.y += 0.0035 * spin;
    layerA.rotation.z += 0.0012 * spin;
    layerB.rotation.y -= 0.0026 * spin;
    layerB.rotation.x += 0.0018 * spin;
    layerC.rotation.y += 0.0014 * spin;
    arcs.rotation.x += 0.004 * spin;
    sparks.rotation.y -= 0.0015 * spin;

    colorTo.set(speakingNow ? 0x00ffb3 : thinking ? 0x4af0ff : CYAN);
    colorNow.lerp(colorTo, 0.07);
    paint(globe, colorNow);
    core.material.color.copy(colorNow).lerp(new THREE.Color(0xffffff), 0.35);
    glow.material.color.copy(colorNow);
    glow2.material.color.copy(colorNow);

    const pulse = speakingNow
      ? 1 + Math.sin(t / 160) * 0.12
      : thinking
        ? 1 + Math.sin(t / 260) * 0.08
        : 1 + Math.sin(t / 700) * 0.04;
    core.scale.setScalar(pulse);
    marca.lookAt(camera.position);
    marca.scale.setScalar(pulse);
    glow.scale.set(22 * pulse, 22 * pulse, 1);
    glow2.scale.set(110 * pulse, 110 * pulse, 1);
    if (bloomPass) {
      bloomPass.strength = speakingNow ? 0.72 : thinking ? 0.62 : 0.52;
    }

    if (composer) composer.render();
    else renderer.render(scene, camera);
  }

  three = {
    renderer, rafId: 0, controls,
    tick,
    pause() {
      if (three && three.rafId) { cancelAnimationFrame(three.rafId); three.rafId = 0; }
      if (controls) controls.enabled = false;
    },
    resume() {
      if (controls) controls.enabled = true;
      if (three && !three.rafId) three.rafId = requestAnimationFrame(tick);
    }
  };
  three.rafId = requestAnimationFrame(tick);
  } catch (e) {
    console.warn('three.js no disponible:', e);
    if (typeof log === 'function') log('Modo 3D no disponible en este navegador', 'warn');
    const h = document.getElementById('hud');
    if (h) h.querySelectorAll('canvas').forEach(c => c.remove());
    three = null;
  }
}

document.addEventListener('visibilitychange', () => {
  if (!three) return;
  if (document.hidden) three.pause(); else three.resume();
});
