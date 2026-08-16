/**
 * Tutorial de primer arranque de J.A.R.V.I.S.
 *
 * Habla con main.js por el puente `window.jarvis` (ver preload.js). No usa
 * Node directamente: la ventana va con contextIsolation, como el panel.
 */

const $ = (id) => document.getElementById(id);

const PANTALLAS = [...document.querySelectorAll('.pantalla')];
const TOTAL = PANTALLAS.length;
const PASO_INSTALAR = 3;
const PASO_FINAL = 4;

let paso = 0;
let instalando = false;
let instalado = false;

// ---------------------------------------------------------------- pasos

function pintarPips() {
  const cont = $('pasos');
  cont.innerHTML = '';
  for (let i = 0; i < TOTAL; i++) {
    const p = document.createElement('div');
    p.className = 'pip' + (i === paso ? ' activo' : i < paso ? ' hecho' : '');
    cont.appendChild(p);
  }
}

function irA(n) {
  paso = n;
  PANTALLAS.forEach((s, i) => s.classList.toggle('visible', i === n));
  pintarPips();
  document.querySelector('main').scrollTop = 0;

  const siguiente = $('btn-siguiente');
  const atras = $('btn-atras');

  atras.style.display = (n > 0 && n < PASO_INSTALAR) ? '' : 'none';
  $('saltar').style.display = n < PASO_INSTALAR ? '' : 'none';

  if (n === 0) siguiente.textContent = 'EMPEZAR';
  else if (n === PASO_INSTALAR) siguiente.textContent = 'INSTALANDO…';
  else if (n === PASO_FINAL) siguiente.textContent = '✦  ENTRAR';
  else siguiente.textContent = 'SIGUIENTE';

  siguiente.disabled = (n === PASO_INSTALAR && !instalado);
}

// ---------------------------------------------------------------- voz

const VOCES = [
  {
    id: 'jarvis',
    nombre: 'JARVIS',
    detalle: 'La voz original del proyecto. Lista al instante, sin descargas ni GPU.',
  },
  {
    id: 'otra',
    nombre: 'Otra voz de Fish Audio',
    detalle: 'Pega el identificador de cualquier voz de fish.audio (o de una que hayas clonado tú).',
  },
  {
    id: 'alvaro',
    nombre: 'Álvaro — voz de Microsoft',
    detalle: 'Voz masculina en español, sin usar Fish Audio. Suena distinta a JARVIS.',
  },
];

let vozElegida = 'jarvis';

function pintarVoces() {
  const cont = $('voces');
  cont.innerHTML = '';
  for (const v of VOCES) {
    const fila = document.createElement('label');
    fila.className = 'voz' + (v.id === vozElegida ? ' elegida' : '');
    fila.innerHTML = `
      <input type="radio" name="voz" value="${v.id}" ${v.id === vozElegida ? 'checked' : ''}>
      <span class="txt"><b>${v.nombre}</b><small>${v.detalle}</small></span>`;
    fila.querySelector('input').addEventListener('change', () => {
      vozElegida = v.id;
      pintarVoces();
      $('caja-propia').style.display = v.id === 'otra' ? '' : 'none';
      $('av-voz').textContent = '';
    });
    cont.appendChild(fila);
  }
}

$('btn-probar-voz').addEventListener('click', async () => {
  const av = $('av-voz');
  const btn = $('btn-probar-voz');
  const vozId = ($('voz-id').value || '').trim();
  if (vozElegida === 'otra' && !vozId) {
    av.className = 'aviso mal';
    av.textContent = 'Pega primero el identificador de la voz.';
    return;
  }
  btn.disabled = true;
  av.className = 'aviso trabajando';
  av.style.color = '';
  av.textContent = 'Generando…';

  try {
    const r = await window.jarvis.probarVoz({ voz: vozElegida, vozId });
    if (r && r.ok) {
      // El audio llega en base64 y se reproduce aquí, sin archivos sueltos.
      const audio = new Audio('data:' + r.tipo + ';base64,' + r.audio);
      await audio.play();
      if (r.aviso) {
        av.className = 'aviso';
        av.style.color = '#ffb95e';
        av.textContent = '⚠ ' + r.aviso;
      } else {
        av.className = 'aviso ok';
        av.style.color = '';
        av.textContent = '✓ Sonando (' + r.fuente + ')';
      }
    } else {
      av.className = 'aviso mal';
      av.textContent = '✗ ' + ((r && r.error) || 'No se pudo generar la voz');
    }
  } catch (e) {
    av.className = 'aviso mal';
    av.textContent = '✗ ' + e.message;
  }
  btn.disabled = false;
});

// ---------------------------------------------------------------- claves

function recogerClaves() {
  const cerebro = $('k-cerebro').value.trim();
  const datos = {
    DEEPSEEK_API_KEY: cerebro,
    // Sin clave de visión propia, se reutiliza la del cerebro (OpenRouter
    // sirve ambas cosas con la misma).
    OPENROUTER_API_KEY: $('k-vision').value.trim() || cerebro,
    JARVIS_LAT: $('k-lat').value.trim(),
    JARVIS_LON: $('k-lon').value.trim(),
  };
  for (const k of Object.keys(datos)) if (!datos[k]) delete datos[k];
  return datos;
}

/** Deja seguir sin clave, pero avisando de que el chat no irá. */
function validarClaves() {
  const av = $('av-cerebro');
  if ($('k-cerebro').value.trim()) { av.textContent = ''; return true; }
  if (av.dataset.avisado === '1') return true;   // segunda pulsación: pasar
  av.dataset.avisado = '1';
  av.className = 'aviso mal';
  av.textContent = 'Sin esta clave el chat no funcionará. ' +
                   'Pulsa otra vez SIGUIENTE si quieres ponerla más tarde.';
  return false;
}

// ---------------------------------------------------------------- instalación

function pintarTareas(tareas) {
  const cont = $('tareas');
  cont.innerHTML = '';
  for (const t of tareas) {
    const fila = document.createElement('div');
    fila.className = 'tarea ' + t.estado;
    const icono = { espera: '○', activa: '◐', lista: '●', fallo: '✕' }[t.estado] || '○';
    fila.innerHTML = `<span class="icono">${icono}</span><span>${t.texto}</span>`;
    cont.appendChild(fila);
  }
}

/* Máximo de líneas visibles: tiene que cuadrar con --lineas del CSS, o
   sobra media línea cortada por el borde de la caja. */
const LINEAS_CONSOLA = 6;

function log(linea) {
  const c = $('consola');
  const d = document.createElement('div');
  d.textContent = linea;
  c.prepend(d);
  while (c.childElementCount > LINEAS_CONSOLA) c.lastElementChild.remove();
}

async function instalar() {
  instalando = true;
  irA(PASO_INSTALAR);

  await window.jarvis.guardarConfig({
    claves: recogerClaves(),
    voz: { tipo: vozElegida, vozId: ($('voz-id').value || '').trim() },
  });

  const r = await window.jarvis.instalar();

  instalando = false;
  instalado = true;
  if (r && r.aviso) {
    $('sub-instalar').innerHTML = r.aviso;
  }
  irA(PASO_FINAL);
}

/* Progreso que manda main.js. `porcentaje` solo llega cuando se sabe de
   verdad; si no, la barra va en modo indeterminado (nada de inventarse un
   número que no significa nada). */
window.jarvis.alProgreso((d) => {
  if (d.tareas) pintarTareas(d.tareas);
  if (d.linea) log(d.linea);

  const barra = $('barra');
  if (typeof d.porcentaje === 'number') {
    barra.classList.remove('sin-saber');
    $('relleno').style.width = Math.max(0, Math.min(100, d.porcentaje)) + '%';
  } else if (d.indeterminado) {
    barra.classList.add('sin-saber');
  }
});

// ---------------------------------------------------------------- confeti

function lanzarConfeti(ms = 2000) {
  const lienzo = $('confeti');
  const ctx = lienzo.getContext('2d');
  const ancho = lienzo.width = window.innerWidth;
  const alto = lienzo.height = window.innerHeight;
  lienzo.style.display = 'block';

  const COLORES = ['#5eeaff', '#2e96be', '#00ffb3', '#eafcff', '#7fdcff', '#ffffff'];
  const trozos = [];
  // Mucho confeti, como pediste; 320 va suave a 60 fps.
  for (let i = 0; i < 320; i++) {
    trozos.push({
      x: Math.random() * ancho,
      y: -20 - Math.random() * alto * 0.6,
      an: 5 + Math.random() * 7,
      al: 8 + Math.random() * 10,
      color: COLORES[(Math.random() * COLORES.length) | 0],
      vy: 2.6 + Math.random() * 4.4,
      vx: -1.6 + Math.random() * 3.2,
      giro: Math.random() * Math.PI * 2,
      vgiro: -0.22 + Math.random() * 0.44,
    });
  }

  const inicio = performance.now();
  (function cuadro(ahora) {
    const t = ahora - inicio;
    ctx.clearRect(0, 0, ancho, alto);
    // Último medio segundo: se desvanece en vez de cortar de golpe.
    ctx.globalAlpha = t > ms - 500 ? Math.max(0, (ms - t) / 500) : 1;

    for (const p of trozos) {
      p.x += p.vx; p.y += p.vy; p.giro += p.vgiro;
      if (p.y > alto + 20) { p.y = -20; p.x = Math.random() * ancho; }
      ctx.save();
      ctx.translate(p.x, p.y);
      ctx.rotate(p.giro);
      ctx.fillStyle = p.color;
      ctx.fillRect(-p.an / 2, -p.al / 2, p.an, p.al);
      ctx.restore();
    }

    if (t < ms) requestAnimationFrame(cuadro);
    else { ctx.clearRect(0, 0, ancho, alto); lienzo.style.display = 'none'; }
  })(inicio);
}

// ---------------------------------------------------------------- navegación

$('btn-siguiente').addEventListener('click', async () => {
  if (paso === 1 && !validarClaves()) return;

  if (paso === PASO_INSTALAR - 1) return instalar();

  if (paso === PASO_FINAL) {
    const btn = $('btn-siguiente');
    btn.disabled = true;
    lanzarConfeti(2000);
    // Se entra justo cuando acaba el confeti.
    setTimeout(() => window.jarvis.terminar(), 2000);
    return;
  }

  irA(paso + 1);
});

$('btn-atras').addEventListener('click', () => { if (paso > 0) irA(paso - 1); });

$('saltar').addEventListener('click', () => {
  if (confirm('¿Seguro? Podrás configurarlo luego desde Ajustes, pero el chat ' +
              'no funcionará hasta que pongas la clave del cerebro.')) {
    window.jarvis.saltar();
  }
});

// Los enlaces se abren en el navegador de verdad, no dentro de la app.
document.querySelectorAll('[data-abrir]').forEach(a => {
  a.addEventListener('click', (e) => {
    e.preventDefault();
    window.jarvis.abrirEnlace(a.dataset.abrir);
  });
});

pintarVoces();
irA(0);
