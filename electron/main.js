/**
 * J.A.R.V.I.S. — proceso principal de Electron.
 *
 * Arranca el backend FastAPI del panel (puerto 8080) como hijo y muestra
 * el HUD en una ventana nativa. Hermes vive en el portatil Linux; aqui
 * no se lanza. La voz es Fish Audio (nube), no un servidor XTTS local.
 *
 * El backend va en modo kiosco (JARVIS_KIOSK=1): sin login. Es seguro porque
 * solo escucha en localhost y _require_user() comprueba la IP real del socket.
 */
const { app, BrowserWindow, shell, dialog, Menu, ipcMain } = require('electron');
const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');
const http = require('http');

// --- Rutas ---------------------------------------------------------------
//
// Hay DOS raices y no se pueden mezclar:
//
//   ORIGEN — el codigo tal y como viene en el .exe (solo lectura).
//     · Portable: una carpeta TEMPORAL distinta en cada ejecucion.
//     · Instalador: dentro de Program Files, no escribible sin ser admin.
//
//   DATOS — %APPDATA%\J.A.R.V.I.S\, que persiste entre ejecuciones.
//     Ahi van los entornos de Python, el .env y la voz de referencia.
//
// Si los entornos vivieran en ORIGEN, el portable reinstalaria 3 GB CADA VEZ
// que se abre (carpeta temporal nueva) y el instalador ni siquiera podria
// escribirlos. Por eso el codigo se copia una vez a DATOS y se trabaja alli.
// El nombre visible es "J.A.R.V.I.S." (con punto final), pero Windows NO
// admite carpetas terminadas en punto: Electron pediria %APPDATA%\J.A.R.V.I.S.
// y en disco se crearia sin el punto, con lo que las rutas dejan de coincidir
// y las escrituras fallan en silencio. Se fija un nombre de carpeta valido
// ANTES de que nada pida getPath('userData'). El titulo de la ventana y el
// instalador siguen mostrando "J.A.R.V.I.S." — esto solo afecta a la carpeta.
app.setName('JARVIS');

const EMPAQUETADO = app.isPackaged;
const ORIGEN = EMPAQUETADO
  ? path.join(process.resourcesPath, 'app-python')
  : path.join(__dirname, '..');

const PUERTO_PANEL = 8080;

// OJO: app.getPath('userData') NO se puede llamar al cargar el modulo — lanza
// antes de que la app este lista y el proceso muere sin dejar rastro. Por eso
// las rutas que dependen de el se calculan a demanda, no en constantes.
let _raiz = null;
function raiz() {
  if (_raiz) return _raiz;
  // En desarrollo se trabaja sobre el propio proyecto: no hay nada que copiar.
  _raiz = EMPAQUETADO ? path.join(carpetaDatos(), 'app') : ORIGEN;
  return _raiz;
}

const pyPanel = () => path.join(raiz(), 'venv', 'Scripts', 'python.exe');

let ventana = null;
let procPanel = null;
let cerrando = false;

/**
 * Log a archivo.
 *
 * En una app de ventana de Windows, console.log no va a ninguna parte: no hay
 * consola enganchada. Sin esto, un fallo al arrancar deja cero rastro y no hay
 * forma de saber por que la app no abre.
 */
/**
 * Carpeta de datos.
 *
 * OJO con el nombre del producto: "J.A.R.V.I.S." acaba en punto, y Windows NO
 * admite carpetas terminadas en punto — las crea sin el. Electron pide una
 * ruta con punto que en disco se llama sin el, y a partir de ahi cualquier
 * escritura puede fallar de forma silenciosa. Por eso se limpia siempre.
 */
let _datos = null;
function carpetaDatos() {
  if (_datos) return _datos;
  let d = app.getPath('userData');
  // Quitar puntos y espacios finales de cada tramo de la ruta.
  const limpio = d.replace(/[. ]+(?=[\\/]|$)/g, '');
  if (limpio !== d) d = limpio;
  try { fs.mkdirSync(d, { recursive: true }); } catch (e) { /* se vera luego */ }
  _datos = d;
  return d;
}

const rutaLog = () => path.join(carpetaDatos(), 'jarvis.log');
function log(...partes) {
  const linea = `[${new Date().toISOString()}] ${partes.join(' ')}`;
  console.log(linea);
  try {
    const r = rutaLog();
    fs.mkdirSync(path.dirname(r), { recursive: true });
    fs.appendFileSync(r, linea + '\n');
  } catch (e) {
    // Ultimo recurso: %TEMP% siempre se puede escribir. Sin esto, un fallo
    // de rutas deja cero rastro y la app "no abre" sin explicacion.
    try {
      fs.appendFileSync(path.join(require('os').tmpdir(), 'jarvis.log'),
                        linea + '\n');
    } catch (x) { /* nada mas que hacer */ }
  }
}

// Un fallo no capturado dejaba la app abierta sin ventana y sin explicacion.
process.on('uncaughtException', (e) => {
  log('ERROR no capturado:', e && e.stack ? e.stack : String(e));
  try {
    dialog.showErrorBox('J.A.R.V.I.S.',
      'Error inesperado al arrancar:\n\n' + (e && e.message ? e.message : String(e)) +
      `\n\nDetalles en:\n${rutaLog()}`);
  } catch (x) { /* dialog puede no estar listo todavia */ }
  app.exit(1);
});

// --- Utilidades ----------------------------------------------------------

/** Version instalada en DATOS, para saber si el .exe trae uno mas nuevo. */
function rutaVersion() {
  return path.join(raiz(), '.version');
}

/**
 * Copia recursiva saltando lo que pertenece al usuario.
 * venv: 3 GB. voz-jarvis: puede ser la del usuario. .env: claves.
 * memoria: recuerdos; solo se copia si el destino no existe.
 */
function copiarOrigen(desde, hasta) {
  for (const entrada of fs.readdirSync(desde, { withFileTypes: true })) {
    const org = path.join(desde, entrada.name);
    const dst = path.join(hasta, entrada.name);
    if (entrada.isDirectory()) {
      if (entrada.name === 'venv' || entrada.name === '__pycache__') continue;
      if (entrada.name === 'voz-jarvis' && fs.existsSync(dst)) continue;
      if (entrada.name === 'memoria' && fs.existsSync(dst)) continue;
      fs.mkdirSync(dst, { recursive: true });
      copiarOrigen(org, dst);
    } else {
      if (entrada.name === '.env' && fs.existsSync(dst)) continue;
      try {
        fs.copyFileSync(org, dst);
      } catch (e) {
        console.warn('[jarvis] No se pudo copiar', entrada.name, e.message);
      }
    }
  }
}

/**
 * El HUD y el backend SIEMPRE salen del .exe, aunque la version coincida.
 * Si no, un 1.0.0 viejo en %APPDATA% tapa un 1.0.0 recompilado.
 */
function refrescarCodigo() {
  const srcApp = path.join(ORIGEN, 'app');
  const dstApp = path.join(raiz(), 'app');
  if (!fs.existsSync(srcApp)) return;
  log('Actualizando HUD y backend desde el .exe');
  fs.mkdirSync(dstApp, { recursive: true });
  copiarOrigen(srcApp, dstApp);
  const srcPer = path.join(ORIGEN, 'personalidades');
  if (fs.existsSync(srcPer)) {
    const dstPer = path.join(raiz(), 'personalidades');
    fs.mkdirSync(dstPer, { recursive: true });
    copiarOrigen(srcPer, dstPer);
  }
  const req = path.join(ORIGEN, 'requirements.txt');
  if (fs.existsSync(req)) {
    try { fs.copyFileSync(req, path.join(raiz(), 'requirements.txt')); }
    catch (e) { console.warn('[jarvis] requirements.txt', e.message); }
  }
}

/**
 * Copia el codigo de ORIGEN a DATOS la primera vez, y refresca el HUD
 * en cada arranque. No pisa .env, venv ni memoria.
 */
function prepararCarpetaDatos() {
  if (!EMPAQUETADO) return;   // en desarrollo se trabaja sobre el proyecto

  const version = app.getVersion();
  const yaInstalada = fs.existsSync(rutaVersion())
    ? fs.readFileSync(rutaVersion(), 'utf8').trim()
    : null;

  log(`Preparando carpeta de datos (exe ${version}, instalada ${yaInstalada || 'ninguna'})`);
  log('  origen:', ORIGEN);
  log('  destino:', raiz());
  fs.mkdirSync(raiz(), { recursive: true });

  try {
    if (!fs.existsSync(ORIGEN)) {
      throw new Error(`No encuentro los archivos de la aplicacion en:\n${ORIGEN}`);
    }
    if (yaInstalada !== version) {
      copiarOrigen(ORIGEN, raiz());
      fs.writeFileSync(rutaVersion(), version, 'utf8');
      log('Carpeta de datos lista (copia completa).');
    } else {
      refrescarCodigo();
    }
    if (!fs.existsSync(path.join(raiz(), 'app', 'main.py'))) {
      throw new Error('La copia quedo incompleta: falta app/main.py');
    }
  } catch (e) {
    log('FALLO preparando la carpeta de datos:', e.message);
    dialog.showErrorBox('J.A.R.V.I.S.',
      'No se pudo preparar la carpeta de datos:\n\n' + e.message +
      `\n\nOrigen: ${ORIGEN}\nDestino: ${raiz()}`);
    throw e;
  }
}

/** Ruta del .env. Siempre en DATOS, que es donde se puede escribir. */
function rutaEnv() {
  return path.join(raiz(), '.env');
}

/** Lee el .env y lo devuelve como objeto (mismo formato que start.bat). */
function leerEnv() {
  const vars = {};
  const ruta = rutaEnv();
  if (!fs.existsSync(ruta)) return vars;
  for (const linea of fs.readFileSync(ruta, 'utf8').split(/\r?\n/)) {
    const t = linea.trim();
    if (!t || t.startsWith('#')) continue;
    const i = t.indexOf('=');
    if (i < 1) continue;
    const valor = t.slice(i + 1).trim();
    if (valor) vars[t.slice(0, i).trim()] = valor;
  }
  return vars;
}

/** Resuelve cuando el puerto responde, o rechaza al agotar los intentos. */
function esperarPuerto(puerto, ruta, intentos, esperaMs) {
  return new Promise((resolve, reject) => {
    let n = 0;
    const probar = () => {
      if (cerrando) return reject(new Error('cerrando'));
      const req = http.get(
        { host: '127.0.0.1', port: puerto, path: ruta, timeout: 2000 },
        (res) => { res.resume(); resolve(); }
      );
      req.on('error', reintentar);
      req.on('timeout', () => { req.destroy(); reintentar(); });
    };
    const reintentar = () => {
      if (++n >= intentos) return reject(new Error(`puerto ${puerto} no responde`));
      setTimeout(probar, esperaMs);
    };
    probar();
  });
}

/**
 * Ejecuta un comando y resuelve con su codigo de salida.
 *
 * Si se pasa `alLog`, cada linea de salida se le reenvia: durante la
 * instalacion es lo unico que demuestra que la cosa avanza y no se ha
 * colgado (pip puede tirarse minutos sin decir nada).
 */
function ejecutar(cmd, args, cwd, alLog) {
  return new Promise((resolve) => {
    const p = spawn(cmd, args, { cwd, windowsHide: true });
    const trocear = (buf) => {
      const texto = buf.toString();
      process.stdout.write('[setup] ' + texto);
      if (!alLog) return;
      for (const l of texto.split(/\r?\n/)) {
        const t = l.trim();
        if (t) alLog(t);
      }
    };
    p.stdout.on('data', trocear);
    p.stderr.on('data', trocear);
    p.on('exit', resolve);
    p.on('error', () => resolve(-1));
  });
}

/** Busca el python del sistema (los venv se crean con el). */
let PY_SISTEMA = null;
function pythonDelSistema() {
  if (PY_SISTEMA) return PY_SISTEMA;
  for (const cmd of ['python', 'py']) {
    try {
      const r = require('child_process').spawnSync(cmd, ['--version'], { windowsHide: true });
      if (r.status === 0) return (PY_SISTEMA = cmd);
    } catch (e) { /* siguiente */ }
  }
  return null;
}

/**
 * Crea los entornos de Python la primera vez que se abre la app.
 *
 * No se empaquetan en el instalador a proposito: con torch y CUDA dentro,
 * el .exe pasaria de ~90 MB a varios GB. Se montan aqui una sola vez.
 */
/**
 * ¿Falta montar algún entorno? (se consulta ANTES de abrir la ventana)
 *
 * No basta con que exista python.exe: si la descarga de PyTorch se corta a
 * medias, el venv queda creado pero sin torch, y entonces el motor de voz no
 * arranca y JARVIS habla con la voz de reserva sin decir por que. Se mira que
 * torch este realmente ahi.
 */
function hayQuePreparar() {
  return !fs.existsSync(pyPanel());
}

/**
 * Instala lo que falte, informando del avance al tutorial.
 *
 * Sobre el progreso: pip no da un porcentaje global fiable, asi que la barra
 * solo avanza al completar cada tarea (eso SI es real). Mientras una tarea
 * esta en marcha se pone en modo indeterminado — nunca un numero inventado.
 *
 * Devuelve {ok, aviso}. Que falle la voz no aborta nada: voice.py cae solo
 * a la voz de reserva.
 */
async function instalarDependencias() {
  // Solo el entorno del panel: la voz va por Fish Audio (nube) y no necesita
  // instalar nada � ni PyTorch, ni modelos, ni GPU.
  if (fs.existsSync(pyPanel())) return { ok: true };

  // Sin -q: pip va diciendo que descarga, y eso es lo que se pinta en la
  // consolita para que se vea que avanza. --no-cache-dir evita que pip
  // serialice los wheels en memoria (revienta con los grandes).
  const PIP = ['-m', 'pip', 'install', '--no-cache-dir', '--progress-bar', 'off'];

  const tareas = [
    { id: 'venv', texto: 'Preparar el entorno', estado: 'espera' },
    { id: 'deps', texto: 'Descargar las dependencias', estado: 'espera' },
  ];

  let hechas = 0;
  const empujar = (extra = {}) => progreso({ tareas, ...extra });
  const linea = (l) => progreso({ linea: l });

  /** Marca una tarea, la ejecuta y actualiza la barra con avance real. */
  async function tarea(id, cmd, args, cwd) {
    const t = tareas.find((x) => x.id === id);
    t.estado = 'activa';
    // Mientras corre no se sabe el porcentaje: barra indeterminada.
    empujar({ indeterminado: true });
    const cod = await ejecutar(cmd, args, cwd, linea);
    t.estado = cod === 0 ? 'lista' : 'fallo';
    hechas++;
    // Al terminar si hay un dato real que ensenar: tareas completadas.
    empujar({ porcentaje: Math.round((hechas / tareas.length) * 100) });
    return cod;
  }

  empujar({ porcentaje: 0 });

  // El pip que trae Python 3.10 (21.x) da problemas con wheels grandes:
  // se actualiza siempre nada mas crear el entorno.
  await tarea('venv', PY_SISTEMA, ['-m', 'venv', 'venv'], raiz());
  if (fs.existsSync(pyPanel())) {
    await ejecutar(pyPanel(), ['-m', 'pip', 'install', '--upgrade', 'pip',
                               '--quiet', '--no-cache-dir'], raiz(), linea);
  }

  const cod = await tarea('deps', pyPanel(),
                          [...PIP, '-r', 'requirements.txt'], raiz());
  if (cod !== 0 || !fs.existsSync(pyPanel())) {
    return { ok: false, error: 'No se pudieron instalar las dependencias.' };
  }

  return { ok: true };
}

/**
 * Manda un estado a la pantalla de carga (si sigue viva).
 *
 * `opts.detalle` es la linea pequena de debajo (lo que escupe pip).
 * `opts.paso` / `opts.total` pintan la barra de progreso.
 */
function estado(texto, opts = {}) {
  console.log('[jarvis]', texto);
  if (!ventana || ventana.isDestroyed()) return;
  const carga = JSON.stringify({ texto, ...opts });
  ventana.webContents
    .executeJavaScript(`window.jarvisEstado && window.jarvisEstado(${carga});`)
    .catch(() => {});
}

/** Manda progreso de instalación al tutorial (por IPC, no por executeJavaScript). */
function progreso(datos) {
  if (ventana && !ventana.isDestroyed()) {
    ventana.webContents.send('tutorial:progreso', datos);
  }
}

// --- Tutorial de primer arranque -----------------------------------------

/** Marcador de "ya configurado". Si existe, el tutorial no vuelve a salir. */
function rutaMarcador() {
  return path.join(carpetaDatos(), 'configurado.json');
}

function yaConfigurado() {
  return fs.existsSync(rutaMarcador());
}

function marcarConfigurado(datos = {}) {
  try {
    fs.mkdirSync(carpetaDatos(), { recursive: true });
    fs.writeFileSync(rutaMarcador(),
      JSON.stringify({ fecha: new Date().toISOString(), ...datos }, null, 2));
  } catch (e) {
    console.warn('[jarvis] No se pudo guardar el marcador:', e.message);
  }
}

/** Escribe claves en el .env conservando comentarios y orden. */
function guardarEnEnv(cambios) {
  const ruta = rutaEnv();
  let lineas = fs.existsSync(ruta)
    ? fs.readFileSync(ruta, 'utf8').split(/\r?\n/)
    : [];

  const pendientes = { ...cambios };
  lineas = lineas.map((linea) => {
    const t = linea.trim();
    if (!t || t.startsWith('#') || !t.includes('=')) return linea;
    const k = t.slice(0, t.indexOf('=')).trim();
    if (!(k in pendientes)) return linea;
    const v = pendientes[k];
    delete pendientes[k];
    return `${k}=${v}`;
  });

  const extra = Object.entries(pendientes);
  if (extra.length) {
    lineas.push('', '# --- Anadido durante la configuracion inicial ---');
    for (const [k, v] of extra) lineas.push(`${k}=${v}`);
  }

  fs.mkdirSync(path.dirname(ruta), { recursive: true });
  fs.writeFileSync(ruta, lineas.join('\n') + '\n', 'utf8');
}

/**
 * Deja lista la voz elegida.
 *
 * 'jarvis' usa la voz por defecto de Fish Audio; 'otra' permite pegar el id
 * de cualquier voz de fish.audio; 'alvaro' deja Fish sin id y hace que
 * voice.py caiga a la voz de reserva de Microsoft.
 */
function aplicarVoz(voz) {
  if (!voz || !voz.tipo) return;

  const cambios = {};
  if (voz.tipo === 'alvaro') {
    // Sin clave, voice.py se salta Fish y pasa a la voz de reserva.
    cambios.FISH_API_KEY = '';
  } else if (voz.tipo === 'otra' && voz.vozId) {
    cambios.FISH_VOICE_ID = voz.vozId.trim();
  }
  if (Object.keys(cambios).length) guardarEnEnv(cambios);
}

/** Ventana del tutorial. Resuelve cuando el usuario termina o lo salta. */
function abrirTutorial() {
  return new Promise((resolve) => {
    ventana = new BrowserWindow({
      width: 780, height: 760,
      minWidth: 660, minHeight: 620,
      show: true,
      backgroundColor: '#050810',
      autoHideMenuBar: true,
      icon: path.join(__dirname, 'build', 'icon.ico'),
      title: 'J.A.R.V.I.S.',
      webPreferences: {
        preload: path.join(__dirname, 'preload.js'),
        nodeIntegration: false,
        contextIsolation: true,
        spellcheck: false,
      },
    });

    ventana.webContents.on('did-fail-load', (_e, code, desc) => {
      console.error(`[jarvis] No cargo el tutorial: ${code} ${desc}`);
    });
    ventana.loadFile(path.join(__dirname, 'tutorial.html'));

    let resuelto = false;
    const acabar = (r) => {
      if (resuelto) return;
      resuelto = true;
      for (const canal of ['tutorial:guardar', 'tutorial:instalar',
                           'tutorial:probar-voz',
                           'tutorial:abrir-enlace', 'tutorial:terminar',
                           'tutorial:saltar']) {
        ipcMain.removeHandler(canal);
      }
      resolve(r);
    };

    // Cerrar la ventana a mitad = salir de la app (no seguir a medias).
    ventana.on('closed', () => { ventana = null; acabar({ cerrado: true }); });

    let vozElegida = null;

    ipcMain.handle('tutorial:guardar', (_e, datos) => {
      if (datos.claves && Object.keys(datos.claves).length) {
        guardarEnEnv(datos.claves);
      }
      vozElegida = datos.voz;
      aplicarVoz(datos.voz);
      return { ok: true };
    });

    ipcMain.handle('tutorial:instalar', async () => {
      const quiereVoz = !vozElegida || vozElegida.tipo !== 'alvaro';
      const r = await instalarDependencias(quiereVoz);
      if (!r.ok) {
        dialog.showErrorBox('J.A.R.V.I.S.',
          (r.error || 'Fallo la instalacion.') +
          '\n\nComprueba tu conexion a internet y vuelve a abrir la aplicacion.');
      }
      return r;
    });

    ipcMain.handle('tutorial:probar-voz', async (_e, opts) => probarVoz(opts));

    ipcMain.handle('tutorial:abrir-enlace', (_e, url) => {
      // Solo http(s): que un enlace no pueda lanzar nada del sistema.
      if (/^https?:\/\//i.test(url)) shell.openExternal(url);
    });

    ipcMain.handle('tutorial:terminar', () => {
      marcarConfigurado({ voz: vozElegida ? vozElegida.tipo : 'jarvis' });
      acabar({ ok: true });
    });

    ipcMain.handle('tutorial:saltar', () => {
      marcarConfigurado({ saltado: true });
      acabar({ ok: true, saltado: true });
    });
  });
}

/**
 * Genera una frase de prueba para el botón "probar voz" del tutorial.
 *
 * Reutiliza app/voice.py (misma cadena de fallbacks que el panel), asi que
 * lo que se oye aqui es exactamente lo que sonara luego.
 */
function probarVoz(opts = {}) {
  return new Promise((resolve) => {
    if (!fs.existsSync(pyPanel())) {
      return resolve({ ok: false, error: 'El panel aún no está instalado.' });
    }
    // Probar no debe tocar el .env: se pasa la eleccion por variables de
    // entorno solo para este proceso. Si el usuario prueba y luego cambia de
    // idea, no queda nada guardado.
    const env = { ...process.env, ...leerEnv(), PYTHONIOENCODING: 'utf-8' };
    if (opts.voz === 'alvaro') {
      env.FISH_API_KEY = '';               // sin clave -> voz de reserva
    } else if (opts.voz === 'otra' && opts.vozId) {
      env.FISH_VOICE_ID = String(opts.vozId).trim();
    }

    const codigo =
      'import base64,json;from app import voice;' +
      "w,c,f=voice.tts('Buenas tardes, señor. Todos los sistemas están operativos.');" +
      "print(json.dumps({'ok':bool(w),'audio':base64.b64encode(w).decode() if w else '','tipo':c or '','fuente':f}))";

    const p = spawn(pyPanel(), ['-c', codigo], { cwd: raiz(), env, windowsHide: true });
    let salida = '';
    p.stdout.on('data', (d) => { salida += d.toString(); });
    p.stderr.on('data', (d) => process.stderr.write('[voz-prueba] ' + d));
    p.on('exit', () => {
      try {
        // La última línea es el JSON; lo anterior puede ser ruido de imports.
        const ultima = salida.trim().split(/\r?\n/).pop();
        const r = JSON.parse(ultima);
        // Avisar si sonó otra voz: sin esto el usuario cree que la de Fish
        // suena así y en realidad está oyendo la de reserva.
        if (r.ok && opts.voz !== 'alvaro' && r.fuente !== 'fish') {
          r.aviso = 'Fish Audio no respondió: suena la voz de reserva. ' +
                    'Comprueba tu conexión y la clave.';
        }
        resolve(r);
      } catch (e) {
        resolve({ ok: false, error: 'No se pudo generar la voz.' });
      }
    });
    p.on('error', () => resolve({ ok: false, error: 'No se pudo lanzar el generador.' }));
  });
}

// --- Arranque del backend -------------------------------------------------
//
// Antes habia tambien un servidor de voz local (XTTS) que tardaba 30 s en
// cargar el modelo en la GPU. Ahora la voz va por Fish Audio, asi que solo
// queda un proceso hijo: el panel.

function arrancarPanel(env) {
  const p = spawn(pyPanel(),
                  ['-m', 'uvicorn', 'app.main:app',
                   '--host', '127.0.0.1', '--port', String(PUERTO_PANEL)],
                  { cwd: raiz(), env });
  p.stdout.on('data', (d) => process.stdout.write('[panel] ' + d));
  p.stderr.on('data', (d) => process.stderr.write('[panel] ' + d));
  p.on('exit', (code) => {
    if (!cerrando) {
      dialog.showErrorBox('J.A.R.V.I.S.',
        `El servidor del panel se ha detenido (codigo ${code}).\n\n` +
        'Revisa que el .env sea correcto y vuelve a abrir la aplicacion.');
      app.quit();
    }
  });
  return p;
}

// --- Ventana -------------------------------------------------------------

function crearVentana() {
  // 1600x900 por defecto. Si la pantalla es más pequeña, se ajusta a lo que
  // quepa (con 1600 fijos en un portátil de 1366 la ventana se saldría).
  const { width: anchoPantalla, height: altoPantalla } =
    require('electron').screen.getPrimaryDisplay().workAreaSize;

  ventana = new BrowserWindow({
    width: Math.min(1600, anchoPantalla),
    height: Math.min(900, altoPantalla),
    minWidth: 1024,
    minHeight: 700,
    center: true,
    show: false,
    backgroundColor: '#050810',
    autoHideMenuBar: true,
    icon: path.join(__dirname, 'build', 'icon.ico'),
    title: 'J.A.R.V.I.S.',
    webPreferences: {
      // El panel no necesita Node: mantenerlo apagado es lo seguro.
      nodeIntegration: false,
      contextIsolation: true,
      spellcheck: false,
      autoplayPolicy: 'no-user-gesture-required',
    },
  });

  ventana.once('ready-to-show', () => ventana.show());
  ventana.on('closed', () => { ventana = null; });

  // Micro y cámara: Electron no pregunta como Chrome; hay que concederlas.
  ventana.webContents.session.setPermissionRequestHandler((_wc, permission, callback) => {
    callback(permission === 'media' || permission === 'audioCapture' || permission === 'videoCapture');
  });
  ventana.webContents.session.setPermissionCheckHandler((_wc, permission) => {
    return permission === 'media' || permission === 'audioCapture' || permission === 'videoCapture';
  });

  // Los enlaces externos van al navegador, no abren ventanas de Electron.
  ventana.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: 'deny' };
  });

  ventana.loadFile(path.join(__dirname, 'cargando.html'));
}

// --- Ciclo de vida -------------------------------------------------------

/** Menu minimo: recargar, config y devtools. Sin el, el .env queda enterrado. */
function montarMenu() {
  Menu.setApplicationMenu(Menu.buildFromTemplate([{
    label: 'J.A.R.V.I.S.',
    submenu: [
      {
        label: 'Abrir configuración (.env)',
        click: () => shell.openPath(rutaEnv()),
      },
      {
        label: 'Carpeta de datos',
        click: () => shell.openPath(carpetaDatos()),
      },
      {
        label: 'Estado del sistema…',
        click: () => dialog.showMessageBox({
          type: 'info',
          title: 'J.A.R.V.I.S.',
          message: 'Estado',
          detail:
            `Version: ${app.getVersion()}\n` +
            `Datos: ${raiz()}\n\n` +
            `Panel: ${fs.existsSync(pyPanel()) ? 'instalado' : 'FALTA'}\n` +
            `Voz: Fish Audio ${leerEnv().FISH_API_KEY ? '(configurada)' : '(SIN CLAVE)'}\n` +
            `Log: ${rutaLog()}`,
        }),
      },
      {
        label: 'Repetir la configuraci�n inicial�',
        click: () => repetirTutorial(),
      },
      { type: 'separator' },
      { label: 'Recargar', accelerator: 'F5', role: 'reload' },
      { label: 'Consola', accelerator: 'F12', role: 'toggleDevTools' },
      { type: 'separator' },
      { label: 'Salir', accelerator: 'Alt+F4', role: 'quit' },
    ],
  }]));
}


/** Borra el marcador y reinicia para que vuelva a salir el tutorial. */
function repetirTutorial() {
  const r = dialog.showMessageBoxSync({
    type: 'question',
    title: 'J.A.R.V.I.S.',
    message: '¿Repetir la configuración inicial?',
    detail: 'Se reiniciará la aplicación y volverá a salir el tutorial.\n\n' +
            'Tus claves NO se borran: aparecerán ya puestas y podrás cambiarlas.',
    buttons: ['Repetir', 'Cancelar'],
    defaultId: 0, cancelId: 1,
  });
  if (r === 1) return;
  try { fs.unlinkSync(rutaMarcador()); } catch (e) { /* ya no estaba */ }
  pararHijos();
  app.relaunch();
  app.exit(0);
}

async function iniciar() {
  log('=== arrancando J.A.R.V.I.S.', app.getVersion(), '===');
  log('empaquetado:', EMPAQUETADO, '| origen:', ORIGEN);
  montarMenu();

  // Copiar el codigo a %APPDATA% antes de nada: en el portable, ORIGEN es una
  // carpeta temporal que desaparece, y en el instalador no se puede escribir.
  try {
    prepararCarpetaDatos();
  } catch (e) {
    return app.quit();
  }

  log('configurado:', yaConfigurado(), '| falta instalar:', hayQuePreparar());

  // Primera vez (o si se pide repetir desde Ajustes): tutorial de configuracion.
  // El tutorial se encarga tambien de instalar, con su barra de progreso.
  if (!yaConfigurado() || hayQuePreparar()) {
    if (!pythonDelSistema()) {
      dialog.showErrorBox('J.A.R.V.I.S. — falta Python',
        'No encuentro Python en el sistema.\n\n' +
        'Instalalo desde https://www.python.org/downloads/ ' +
        '(marca "Add Python to PATH") y vuelve a abrir la aplicacion.');
      return app.quit();
    }
    const r = await abrirTutorial();
    if (r && r.cerrado) return app.quit();   // cerro la ventana a mitad
    if (ventana && !ventana.isDestroyed()) {
      ventana.loadFile(path.join(__dirname, 'cargando.html'));
    }
  } else {
    crearVentana();
  }

  const env = {
    ...process.env,
    ...leerEnv(),
    JARVIS_KIOSK: '1',          // sin login (solo escucha en 127.0.0.1)
    JARVIS_COOKIE_SECURE: '0',
    // Para que el panel de ajustes escriba en el .env correcto: empaquetado,
    // el de resources/ vive en Program Files y no se puede tocar sin admin.
    JARVIS_ENV_FILE: rutaEnv(),
    // Para que Ajustes > "repetir configuracion" pueda borrar el marcador.
    JARVIS_MARCADOR_CONFIG: rutaMarcador(),
    PYTHONIOENCODING: 'utf-8',  // que los acentos de los logs no revienten
  };

  estado('Arrancando el panel�');
  procPanel = arrancarPanel(env);

  try {
    await esperarPuerto(PUERTO_PANEL, '/api/ping', 60, 500);  // hasta 30 s
  } catch (e) {
    if (cerrando) return;
    dialog.showErrorBox('J.A.R.V.I.S.', 'El panel no ha arrancado a tiempo.');
    return app.quit();
  }

  estado('Listo.');
  log('panel listo, mostrando la interfaz');
  if (ventana && !ventana.isDestroyed()) {
    ventana.loadURL(`http://127.0.0.1:${PUERTO_PANEL}/?t=${Date.now()}`);
  }
}

function pararHijos() {
  cerrando = true;
  if (procPanel && !procPanel.killed) {
    // taskkill /T se lleva tambien los subprocesos que uvicorn deja abiertos.
    try {
      spawn('taskkill', ['/pid', String(procPanel.pid), '/f', '/t'],
            { windowsHide: true });
    } catch (e) {
      try { procPanel.kill(); } catch (_) {}
    }
  }
  procPanel = null;
}

// Una sola instancia: si ya hay una abierta, se enfoca en vez de duplicar.
if (!app.requestSingleInstanceLock()) {
  // Ojo: esto tambien salta si quedo un lock huerfano de un cierre anterior.
  // Se deja constancia, que si no la app "no abre" sin ninguna explicacion.
  try {
    fs.appendFileSync(path.join(carpetaDatos(), 'jarvis.log'),
      `[${new Date().toISOString()}] Ya habia otra instancia: se cierra esta.\n`);
  } catch (e) { /* nada que hacer */ }
  app.quit();
} else {
  app.on('second-instance', () => {
    if (ventana) {
      if (ventana.isMinimized()) ventana.restore();
      ventana.focus();
    }
  });
  app.whenReady()
    .then(iniciar)
    .catch((e) => {
      log('FALLO en iniciar():', e && e.stack ? e.stack : String(e));
      dialog.showErrorBox('J.A.R.V.I.S.',
        'No se pudo arrancar:\n\n' + (e && e.message ? e.message : String(e)));
      app.exit(1);
    });
}

app.on('window-all-closed', () => { pararHijos(); app.quit(); });
app.on('before-quit', pararHijos);
process.on('exit', pararHijos);
