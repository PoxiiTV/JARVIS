# Mejoras de frontend y voz — Plan de implementación

> **Para agentes:** SUB-SKILL OBLIGATORIA: usar superpowers:subagent-driven-development (recomendado) o superpowers:executing-plans para implementar tarea a tarea. Los pasos usan casillas (`- [ ]`) para seguimiento.

**Objetivo:** Arreglar los fallos visibles del panel (CPU/RAM, parpadeo del login, restos del navegador), añadir un modo de escucha por palabra clave y refinar el HUD sin romper lo que ya funciona.

**Arquitectura:** El panel es un único `app/static/index.html` (HTML + CSS + JS en un archivo, ~2200 líneas) servido por FastAPI y mostrado dentro de Electron. Los cambios son quirúrgicos sobre ese archivo más `app/services.py` (métricas) y `app/main.py` (ajustes). No se introducen dependencias nuevas: el modo escucha usa `webkitSpeechRecognition`, que Chromium ya trae.

**Stack:** FastAPI · Electron 33 · JS sin framework · Three.js (núcleo 3D) · psutil · Fish Audio

**Spec:** este documento (los requisitos vienen de la petición del usuario, recogidos en "Requisitos" más abajo)

## Requisitos

Literales de la petición, cada uno con la tarea que lo cubre:

1. Quitar el sistema de "pulsa para reproducir audio" (era para navegador) → **Tarea 2**
2. Quitar el botón de Estudio de TTS → **Tarea 3**
3. Ajustes: modelo de voz por id, velocidad, y presets guardables → **Tarea 6**
4. La ventana de ajustes se corta si es pequeña → **Tarea 5**
5. No lee CPU, RAM ni disco → **Tarea 1**
6. Consola de sistema más grande → **Tarea 4**
7. Mejorar el núcleo central y el frontend en general → **Tareas 7 y 8**
8. Dos modos de voz: pulsar para hablar (actual) y modo escucha con "Jarvis…" + 3 s de silencio → **Tarea 9**
9. El panel de login aparece medio segundo al abrir → **Tarea 2**

## Restricciones globales

- **Idioma:** todo el texto visible en español de España. Los comentarios del código, en español y sin acentos raros (el archivo ha tenido problemas de codificación: guardar siempre en UTF-8 sin BOM).
- **Sin dependencias nuevas.** Ni npm ni pip. El modo escucha usa `webkitSpeechRecognition` (incluido en Chromium/Electron).
- **No romper el modo web.** El panel también se sirve por navegador con login: los cambios que quiten el desbloqueo de audio deben mirar `kiosk`, no eliminarlo a ciegas.
- **Estilo:** HUD Iron Man refinado. Se mantiene la paleta cian (`#00d4ff`, `#7fd4ee`, acento `#00ffb3`) y la tipografía Consolas para datos. Se mejora jerarquía, espaciado y animaciones — no se cambia de lenguaje visual.
- **Un archivo:** `app/static/index.html` ya es grande, pero el proyecto entero está montado así. No se parte en módulos en este plan; hacerlo obligaría a tocar el empaquetado y no aporta al objetivo.
- **Verificación:** cada tarea se comprueba de verdad (arrancando el panel o con un script), no "debería funcionar".

## Cómo probar durante todo el plan

Arrancar el panel en un puerto de pruebas, sin tocar el 8080 de la app:

```bat
:: guardar como _dev.bat en la raiz (esta en .gitignore por el prefijo _)
@echo off
cd /d "F:\jarvismejorao"
for /f "usebackq eol=# tokens=1,* delims==" %%a in (".env") do (
    if not "%%~b"=="" set "%%a=%%b"
)
set "JARVIS_KIOSK=1"
venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8095 --reload
```

Luego abrir `http://127.0.0.1:8095` en Chrome. Con `--reload`, los cambios en Python se recargan solos; para el HTML basta con refrescar (Ctrl+F5).

---

### Tarea 1: CPU, RAM y disco en Windows

**Ficheros:**
- Modificar: `app/services.py:41-70` (`system_metrics`)
- Test: `tests/test_system_metrics.py` (crear)

**Interfaces:**
- Consume: nada
- Produce: `system_metrics()` devuelve `{cpu, mem, disk, uptime}` con `cpu`/`mem`/`disk` como porcentajes (float 0-100) y `uptime` como texto (`"3d 4h 12m"`). En error devuelve `{"error": str}`.

El bug: la función usa `disk_usage("/")` y lee `/proc/uptime`, que solo existen en Linux. Además la ruta está escrita `"\proc\uptime"` con barras invertidas, donde `\u` es un escape Unicode — o sea, está mal escrita incluso para Linux.

- [ ] **Paso 1: Escribir el test que falla**

Crear `tests/test_system_metrics.py`:

```python
"""Las metricas del sistema tienen que funcionar en Windows y en Linux."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services import system_metrics


def test_metricas():
    m = system_metrics()
    assert "error" not in m, f"devolvio error: {m.get('error')}"
    for clave in ("cpu", "mem", "disk"):
        assert clave in m, f"falta {clave}"
        assert 0 <= m[clave] <= 100, f"{clave} fuera de rango: {m[clave]}"
    assert m["uptime"], "uptime vacio"


if __name__ == "__main__":
    test_metricas()
    print("OK")
```

- [ ] **Paso 2: Ejecutarlo para ver que falla**

Ejecutar: `venv\Scripts\python.exe tests\test_system_metrics.py`
Se espera: `AssertionError: devolvio error: [Errno 2] No such file or directory: '/proc/uptime'`

- [ ] **Paso 3: Arreglar la función**

En `app/services.py`, sustituir el cuerpo de `system_metrics()` por:

```python
def system_metrics():
    """CPU / RAM / disco / uptime. Funciona en Windows y en Linux."""
    try:
        import psutil
        cpu = psutil.cpu_percent(interval=None)
        mem = psutil.virtual_memory()
        # La raiz del disco depende del sistema: "/" en Linux, "C:\" en
        # Windows. psutil.disk_usage("/") revienta en Windows.
        raiz = os.path.abspath(os.sep)
        disk = psutil.disk_usage(raiz)
        # psutil.boot_time() es multiplataforma; /proc/uptime solo existe
        # en Linux (y ademas estaba escrito con barras invertidas).
        uptime_s = max(0.0, time.time() - psutil.boot_time())
        days = int(uptime_s // 86400)
        hours = int((uptime_s % 86400) // 3600)
        mins = int((uptime_s % 3600) // 60)
        if days:
            uptime = f"{days}d {hours}h {mins}m"
        elif hours:
            uptime = f"{hours}h {mins}m"
        else:
            uptime = f"{mins}m"
        return {
            "cpu": round(cpu, 1),
            "mem": round(mem.percent, 1),
            "disk": round(disk.percent, 1),
            "uptime": uptime,
        }
    except Exception as e:
        return {"error": str(e)}
```

Comprobar que `os` y `time` están importados al principio de `services.py`; si falta alguno, añadirlo.

- [ ] **Paso 4: Ejecutar el test**

Ejecutar: `venv\Scripts\python.exe tests\test_system_metrics.py`
Se espera: `OK`

- [ ] **Paso 5: Comprobar que el panel los pinta**

Arrancar `_dev.bat`, abrir `http://127.0.0.1:8095` y mirar el panel SISTEMA: las barras de CPU, RAM y DISCO deben tener valores y UPTIME un texto.

- [ ] **Paso 6: Commit**

```bash
git add app/services.py tests/test_system_metrics.py
git commit -m "fix: las metricas de sistema no funcionaban en Windows"
```

---

### Tarea 2: Fuera el desbloqueo de audio y el parpadeo del login

**Ficheros:**
- Modificar: `app/static/index.html` (bloque `#login` sobre la línea 59, `playAudio`/`unlockAudio`/`activateVoice` sobre la 1935-1967, arranque sobre la 2154)

**Interfaces:**
- Consume: `/api/ping` devuelve `{pong, kiosk, escritorio}` (ya existe)
- Produce: `playAudio(a)` sigue existiendo con la misma firma; en kiosk reproduce directamente

Dos problemas distintos con la misma raíz (código pensado para navegador):

1. Los navegadores bloquean el audio hasta que el usuario interactúa, así que había un "toca para activar la voz". En Electron el autoplay está permitido: sobra.
2. El `#login` está visible en el HTML y se oculta por JS tras la primera petición. Ese hueco es el medio segundo de parpadeo.

- [ ] **Paso 1: Ocultar el login por defecto**

En el CSS de `#login` (sobre la línea 59), añadir `display:none` y una clase que lo muestre:

```css
  #login {
    position:absolute; inset:0; z-index:20; display:none; align-items:center; justify-content:center;
    background:radial-gradient(ellipse at center, rgba(0,40,60,.4), rgba(0,4,9,.97));
    backdrop-filter:blur(6px);
  }
  /* Solo se muestra si el servidor pide sesion. Por defecto oculto: en la
     app de escritorio no hay login, y verlo parpadear al abrir queda fatal. */
  #login.visible { display:flex; }
```

- [ ] **Paso 2: Ajustar quien lo muestra y lo oculta**

Buscar `function showLogin()` (sobre la línea 1313) y cambiarla:

```javascript
function showLogin() { $('login').classList.add('visible'); $('hud-ui').classList.add('hidden'); }
```

En `doLogin()` y en el arranque, donde ponga `$('login').classList.add('hidden')`, cambiarlo por `$('login').classList.remove('visible')`.

- [ ] **Paso 3: Simplificar la reproducción de audio**

Sustituir `playAudio`, `unlockAudio` y `activateVoice` (líneas ~1935-1967) por:

```javascript
/* En la app de escritorio el audio se reproduce sin permiso previo. En
   navegador hay que esperar a que el usuario toque algo, asi que se guarda
   el audio y se ofrece el boton de desbloqueo. */
let enKiosco = false;

function activateVoice() {
  const a = pendingAudio || welcomeAudio;
  pendingAudio = null; welcomeAudio = null;
  hideBoot();
  if (a) {
    const p = a.play();
    if (p && p.catch) p.catch(() => { setSpeaking(false); log('Audio bloqueado: toca la pantalla', 'warn'); });
  }
}

function unlockAudio() {
  document.removeEventListener('pointerdown', unlockAudio);
  document.removeEventListener('keydown', unlockAudio);
  activateVoice();
}

function playAudio(a) {
  const p = a.play();
  if (!p || !p.catch) return;
  p.catch(() => {
    if (enKiosco) { log('No se pudo reproducir el audio', 'warn'); return; }
    pendingAudio = a;
    $('boot-overlay').classList.remove('hidden', 'fade-out');
    showVoiceReady();
    document.addEventListener('pointerdown', unlockAudio);
    document.addEventListener('keydown', unlockAudio);
  });
}
```

- [ ] **Paso 4: Marcar el modo kiosco al arrancar**

En el bloque de arranque (sobre la línea 2154), donde ya se lee `r.kiosk`, guardar el valor:

```javascript
    const r = await apiJSON('/api/ping');
    enKiosco = !!(r && r.kiosk);
    if (enKiosco) $('cfg-logout').classList.add('hidden');
    if (!r || !r.escritorio) $('cfg-tutorial').classList.add('hidden');
    $('login').classList.remove('visible');
    $('hud-ui').classList.remove('hidden');
    boot();
```

- [ ] **Paso 5: Comprobar que no parpadea**

Arrancar `_dev.bat` y abrir el panel varias veces con Ctrl+F5. El recuadro de login no debe aparecer en ningún momento. El saludo debe sonar sin pulsar nada.

- [ ] **Paso 6: Commit**

```bash
git add app/static/index.html
git commit -m "fix: quitar el desbloqueo de audio del navegador y el parpadeo del login"
```

---

### Tarea 3: Quitar el botón de Estudio de TTS

**Ficheros:**
- Modificar: `app/static/index.html:644` (el botón) y `:2149` (su listener)

**Interfaces:**
- Consume: nada
- Produce: nada

El Estudio (`/estudio`) servía para gestionar voces de CosyVoice, que ya no se usa. La ruta del backend se deja: no molesta y quitarla obligaría a tocar más sitios.

- [ ] **Paso 1: Quitar el botón**

Borrar la línea 644:

```html
      <button class="cbtn" id="btn-estudio" title="Estudio de Voz TTS (generar audios)">🎛</button>
```

- [ ] **Paso 2: Quitar su listener**

Borrar la línea 2149:

```javascript
$('btn-estudio').addEventListener('click', () => { window.open('/estudio', '_blank'); });
```

- [ ] **Paso 3: Comprobar que no quedan referencias**

Ejecutar: `Select-String -Path "app\static\index.html" -Pattern "btn-estudio|/estudio"`
Se espera: sin resultados.

- [ ] **Paso 4: Comprobar en el panel**

Recargar y ver que el botón 🎛 ya no está en la barra inferior y que la consola del navegador (F12) no da errores.

- [ ] **Paso 5: Commit**

```bash
git add app/static/index.html
git commit -m "chore: quitar el boton del estudio de voz"
```

---

### Tarea 4: Consola de sistema más grande

**Ficheros:**
- Modificar: `app/static/index.html:317-322` (`#log-shell`) y el `#log` que sigue

**Interfaces:**
- Consume: nada
- Produce: nada

Es donde se lee lo que responde JARVIS, así que se le da bastante más sitio: de 600×128 a 760×260, y texto algo mayor.

- [ ] **Paso 1: Agrandar la consola**

```css
  #log-shell {
    position:absolute; z-index:6; pointer-events:none;
    width:min(760px, calc(100vw - 32px)); height:260px;
    left:16px; bottom:76px;
    display:flex; flex-direction:column; gap:6px;
  }
```

- [ ] **Paso 2: Agrandar el texto**

Localizar la regla `#log {` (sobre la línea 337) y subir `font-size` a `12.5px` y `line-height` a `1.75`. Mantener el resto.

- [ ] **Paso 3: Comprobar que sigue siendo movible**

Recargar. La consola debe verse más grande, y arrastrándola por su título y redimensionándola por la esquina debe seguir funcionando. Con la ventana a 1024 px de ancho no debe salirse.

- [ ] **Paso 4: Commit**

```bash
git add app/static/index.html
git commit -m "feat: consola de sistema mas grande y legible"
```

---

### Tarea 5: El panel de ajustes se corta

**Ficheros:**
- Modificar: `app/static/index.html` (reglas `.cfg-panel` / `.cfg-body`, cerca de la línea 400)

**Interfaces:**
- Consume: nada
- Produce: nada

Con la ventana pequeña, el contenido se sale por abajo y no hay forma de llegar a los botones.

- [ ] **Paso 1: Ver cómo está definido**

Ejecutar: `Select-String -Path "app\static\index.html" -Pattern "\.cfg-panel|\.cfg-body|\.cfg-head" -Context 0,6`

Anotar los nombres reales de las clases y sus alturas: los pasos siguientes las modifican.

- [ ] **Paso 2: Limitar la altura y dar scroll al cuerpo**

En la regla del panel de ajustes, añadir:

```css
    max-height: calc(100vh - 96px);
    display: flex;
    flex-direction: column;
```

Y en el cuerpo (`.cfg-body`):

```css
    overflow-y: auto;
    /* El cuerpo scrollea; la cabecera se queda fija arriba. Sin esto, con la
       ventana pequena los botones de guardar quedan fuera de la pantalla. */
    flex: 1;
    min-height: 0;
```

Añadir también una barra de scroll discreta, a juego con el resto:

```css
  .cfg-body::-webkit-scrollbar { width: 7px; }
  .cfg-body::-webkit-scrollbar-thumb {
    background: rgba(0,212,255,.22); border-radius: 4px;
  }
  .cfg-body::-webkit-scrollbar-thumb:hover { background: rgba(0,212,255,.4); }
```

- [ ] **Paso 3: Comprobar con la ventana pequeña**

Recargar, achicar la ventana a unos 900×600, abrir Ajustes y desplegar CLAVES Y SERVICIOS. Debe poder llegarse a GUARDAR haciendo scroll dentro del panel.

- [ ] **Paso 4: Commit**

```bash
git add app/static/index.html
git commit -m "fix: el panel de ajustes se cortaba con la ventana pequena"
```

---

### Tarea 6: Ajustes de voz — velocidad y presets

**Ficheros:**
- Modificar: `app/main.py` (diccionario `AJUSTES_EDITABLES`, sobre la línea 180)
- Modificar: `app/config.py` (añadir `FISH_SPEED`)
- Modificar: `app/voice.py` (mandar la velocidad a Fish)
- Modificar: `app/static/index.html` (interfaz de presets)

**Interfaces:**
- Consume: `/api/ajustes` (GET y POST) ya existentes
- Produce: `Config.FISH_SPEED` (float, por defecto 1.0); los presets se guardan en `localStorage` bajo la clave `jarvis_voz_presets_v1` como `[{nombre, vozId, velocidad}]`

Los presets van en `localStorage` a propósito: son una comodidad del cliente, no configuración del servidor, y así no hay que tocar el `.env` ni inventar un endpoint nuevo.

- [ ] **Paso 1: Añadir la velocidad a la configuración**

En `app/config.py`, junto a las demás de Fish:

```python
    FISH_SPEED = float(_env("FISH_SPEED", "1.0"))
```

- [ ] **Paso 2: Mandarla en la petición**

En `app/voice.py`, dentro de `_fish()`, añadir la velocidad al `payload`:

```python
    payload = {
        "text": text,
        "reference_id": Config.FISH_VOICE_ID,
        "format": "wav",
        # 1.0 es la velocidad normal. Fish acepta el rango 0.5 - 2.0.
        "prosody": {"speed": max(0.5, min(2.0, Config.FISH_SPEED))},
    }
```

- [ ] **Paso 3: Comprobar que Fish acepta el parámetro**

Ejecutar este script (guardar como `_probar_velocidad.py` en la raíz):

```python
import os, sys, urllib.request, json
sys.path.insert(0, ".")
for linea in open(".env", encoding="utf-8"):
    linea = linea.strip()
    if linea and not linea.startswith("#") and "=" in linea:
        k, v = linea.split("=", 1)
        if v.strip():
            os.environ[k.strip()] = v.strip()

for vel in (0.8, 1.0, 1.4):
    os.environ["FISH_SPEED"] = str(vel)
    for mod in ("app.config", "app.voice"):
        sys.modules.pop(mod, None)
    from app import voice
    w, c, f = voice.tts("Probando la velocidad de la voz.")
    print(f"velocidad {vel}: fuente={f} bytes={len(w) if w else 0}")
```

Ejecutar: `venv\Scripts\python.exe _probar_velocidad.py`
Se espera: las tres líneas con `fuente=fish` y **tamaños distintos** (a más velocidad, menos bytes). Si los tres pesan igual, Fish está ignorando el parámetro: en ese caso quitar `prosody` del payload y anotar en el código que la API no lo admite, dejando el campo de velocidad desactivado en la interfaz.

Borrar `_probar_velocidad.py` al terminar.

- [ ] **Paso 4: Exponer la velocidad en los ajustes**

En `app/main.py`, dentro de `AJUSTES_EDITABLES`, tras `FISH_VOICE_ID`:

```python
    "FISH_SPEED": {"etiqueta": "Velocidad de la voz (0.5 a 2.0)",
                   "secreto": False},
```

Y en el bloque que aplica los cambios en caliente, junto a los demás `Config.`:

```python
    try:
        Config.FISH_SPEED = float(os.environ.get("FISH_SPEED", Config.FISH_SPEED))
    except ValueError:
        pass  # valor no numerico: se deja el anterior
```

- [ ] **Paso 5: Añadir los presets a la interfaz**

En `app/static/index.html`, justo después del `<div id="claves-campos"></div>`, añadir:

```html
            <div class="cfg-sep"></div>
            <label class="presets-tit">Voces guardadas</label>
            <div id="presets-lista"></div>
            <div class="presets-nuevo">
              <input type="text" id="preset-nombre" placeholder="Nombre (ej: JARVIS grave)"
                     autocomplete="off">
              <button class="cfg-btn pequeno" id="preset-guardar">+ GUARDAR ACTUAL</button>
            </div>
```

Estilos, junto a los de `.clave-campo`:

```css
  .presets-tit {
    display:block; font-size:11px; letter-spacing:.6px; font-weight:600;
    color:#9fe4ff; margin-bottom:6px;
  }
  #presets-lista { display:flex; flex-direction:column; gap:6px; margin-bottom:9px; }
  #presets-lista:empty::before {
    content:'Ninguna guardada todavia.';
    font-size:10.5px; color:rgba(168,230,255,.45);
  }
  .preset {
    display:flex; align-items:center; gap:8px; padding:7px 10px;
    border:1px solid rgba(0,212,255,.2); border-radius:7px;
    background:rgba(0,20,34,.55); font-size:11px;
  }
  .preset b { flex:1; color:#d9f6ff; font-weight:600; }
  .preset small { color:rgba(168,230,255,.5); font-family:Consolas,monospace; }
  .preset button {
    border:none; background:none; cursor:pointer; font-size:12px;
    color:rgba(0,212,255,.75); padding:2px 4px;
  }
  .preset button:hover { color:#00ffb3; }
  .preset button.borrar:hover { color:#ff6b6b; }
  .presets-nuevo { display:flex; gap:7px; }
  .presets-nuevo input { flex:1; }
```

Y el JavaScript, junto al resto de la lógica de claves:

```javascript
/* Presets de voz: viven en el navegador (localStorage) porque son una
   comodidad del usuario, no configuracion del servidor. */
const PRESETS_KEY = 'jarvis_voz_presets_v1';

function pintarPresets() {
  const cont = $('presets-lista');
  cont.innerHTML = '';
  for (const [i, p] of lsGet(PRESETS_KEY, []).entries()) {
    const fila = document.createElement('div');
    fila.className = 'preset';
    fila.innerHTML =
      '<b></b><small></small>' +
      '<button title="Usar esta voz">USAR</button>' +
      '<button class="borrar" title="Borrar">✕</button>';
    fila.querySelector('b').textContent = p.nombre;
    fila.querySelector('small').textContent = p.velocidad + '×';
    const [usar, borrar] = fila.querySelectorAll('button');
    usar.addEventListener('click', () => {
      $('k-FISH_VOICE_ID').value = p.vozId;
      $('k-FISH_SPEED').value = p.velocidad;
      const m = $('claves-msg');
      m.className = 'esperando';
      m.textContent = 'Cargada "' + p.nombre + '". Pulsa GUARDAR para aplicarla.';
    });
    borrar.addEventListener('click', () => {
      const l = lsGet(PRESETS_KEY, []);
      l.splice(i, 1);
      lsSet(PRESETS_KEY, l);
      pintarPresets();
    });
    cont.appendChild(fila);
  }
}

$('preset-guardar').addEventListener('click', () => {
  const nombre = $('preset-nombre').value.trim();
  const msg = $('claves-msg');
  if (!nombre) {
    msg.className = 'mal';
    msg.textContent = 'Ponle un nombre a la voz.';
    return;
  }
  const vozId = ($('k-FISH_VOICE_ID') || {}).value || '';
  const velocidad = ($('k-FISH_SPEED') || {}).value || '1.0';
  if (!vozId.trim()) {
    msg.className = 'mal';
    msg.textContent = 'No hay ningun identificador de voz que guardar.';
    return;
  }
  const l = lsGet(PRESETS_KEY, []);
  l.push({ nombre, vozId: vozId.trim(), velocidad: velocidad.trim() });
  lsSet(PRESETS_KEY, l);
  $('preset-nombre').value = '';
  pintarPresets();
  msg.className = 'ok';
  msg.textContent = 'Guardada "' + nombre + '".';
});
```

Llamar a `pintarPresets()` al final de `cargarClaves()`, para que la lista aparezca al abrir el panel.

- [ ] **Paso 6: Probar el ciclo completo**

Recargar, abrir Ajustes → CLAVES Y SERVICIOS. Debe verse el campo de velocidad. Poner `1.3`, guardar un preset con nombre, recargar la página y comprobar que sigue ahí. Pulsar USAR y ver que rellena los campos. GUARDAR y comprobar que el `.env` tiene `FISH_SPEED=1.3`.

- [ ] **Paso 7: Commit**

```bash
git add app/config.py app/voice.py app/main.py app/static/index.html
git commit -m "feat: velocidad de la voz y voces guardadas en ajustes"
```

---

### Tarea 7: Núcleo central

**Ficheros:**
- Modificar: `app/static/index.html` (`#core-label` sobre la línea 300, `#clock-mid` sobre la 288)

**Interfaces:**
- Consume: `setSpeaking(bool)` (ya existe)
- Produce: nada

El núcleo es una bola 3D con un círculo gris de 64 px encima que pone "JARVIS". El reactor está bien; lo que desentona es la etiqueta. Se convierte en un anillo con pulso al hablar, y el reloj gana jerarquía.

- [ ] **Paso 1: Rehacer la etiqueta del núcleo**

```css
  /* ---------- nucleo: anillo sobre el reactor 3D ---------- */
  #core-label {
    position:absolute; left:50%; top:50%; transform:translate(-50%,-50%);
    width:96px; height:96px; border-radius:50%;
    display:flex; align-items:center; justify-content:center;
    font:600 11px Consolas,monospace; letter-spacing:3px;
    color:rgba(234,255,251,.9);
    background:radial-gradient(circle, rgba(0,24,38,.55) 40%, transparent 72%);
    border:1px solid rgba(0,212,255,.3);
    text-shadow:0 0 12px rgba(0,212,255,.8);
    pointer-events:none; z-index:3;
    transition:color .35s ease, border-color .35s ease, box-shadow .35s ease;
  }
  /* Aro exterior girando: da sensacion de "vivo" sin robar atencion */
  #core-label::before {
    content:''; position:absolute; inset:-9px; border-radius:50%;
    border:1px solid transparent;
    border-top-color:rgba(0,212,255,.55);
    border-right-color:rgba(0,212,255,.2);
    animation:coreSpin 7s linear infinite;
  }
  @keyframes coreSpin { to { transform:rotate(360deg); } }

  #core-label.speaking {
    color:#eafffb; border-color:rgba(0,255,179,.85);
    box-shadow:0 0 42px rgba(0,255,179,.45), inset 0 0 26px rgba(0,255,179,.12);
    animation:corePulse 1.5s ease-in-out infinite;
  }
  #core-label.speaking::before {
    border-top-color:#00ffb3; border-right-color:rgba(0,255,179,.35);
    animation-duration:2.2s;
  }
  @keyframes corePulse {
    0%, 100% { transform:translate(-50%,-50%) scale(1); }
    50%      { transform:translate(-50%,-50%) scale(1.045); }
  }

  @media (prefers-reduced-motion: reduce) {
    #core-label::before, #core-label.speaking { animation:none; }
  }
```

- [ ] **Paso 2: Dar jerarquía al reloj**

```css
  #clock-mid .t {
    font-family:'Consolas',monospace; font-size:58px; letter-spacing:6px; font-weight:300;
    background:linear-gradient(180deg,#eafcff,#00d4ff 60%,#0095c8);
    -webkit-background-clip:text; background-clip:text; color:transparent;
    filter:drop-shadow(0 0 22px rgba(0,212,255,.5));
  }
  #clock-mid .d {
    font-family:'Consolas',monospace; font-size:12px; color:rgba(127,212,238,.75);
    letter-spacing:5px; margin-top:9px; text-transform:uppercase;
  }
```

- [ ] **Paso 3: Comprobar que el pulso funciona**

Recargar y mandarle algo a JARVIS. Mientras habla, el anillo debe ponerse verde y latir; al terminar, volver a cian. Comprobar que `setSpeaking(false)` lo devuelve al estado normal.

- [ ] **Paso 4: Commit**

```bash
git add app/static/index.html
git commit -m "feat: nucleo central con anillo y pulso al hablar"
```

---

### Tarea 8: Refinado general del HUD

**Ficheros:**
- Modificar: `app/static/index.html` (reglas `.panel`, `.ph`, `#chatinput`, `.cbtn`)

**Interfaces:**
- Consume: nada
- Produce: nada

Retoques de acabado, sin tocar la estructura ni el JavaScript. Lo que hace que se vea casero: bordes demasiado marcados, cabeceras sin peso y transiciones bruscas.

- [ ] **Paso 1: Suavizar los paneles**

Localizar la regla `.panel {` y ajustar bordes y sombras (no tocar posición ni tamaño):

```css
    border:1px solid rgba(0,212,255,.18);
    border-radius:12px;
    background:linear-gradient(160deg, rgba(0,26,42,.82), rgba(0,14,24,.88));
    box-shadow:0 8px 32px rgba(0,0,0,.45), inset 0 1px 0 rgba(0,212,255,.08);
    transition:border-color .25s ease, box-shadow .25s ease, transform .25s ease;
```

Y al pasar el ratón:

```css
  .panel:hover {
    border-color:rgba(0,212,255,.38);
    box-shadow:0 10px 38px rgba(0,0,0,.5), 0 0 24px rgba(0,212,255,.1),
               inset 0 1px 0 rgba(0,212,255,.12);
  }
```

- [ ] **Paso 2: Cabeceras con más peso**

En la regla `.ph` (cabecera de panel):

```css
    font-size:10.5px; letter-spacing:2.6px; font-weight:600;
    text-transform:uppercase;
    color:rgba(0,212,255,.92);
    padding:11px 13px 9px;
    border-bottom:1px solid rgba(0,212,255,.1);
```

- [ ] **Paso 3: Barra de chat**

```css
  #chatinput {
    border-radius:11px;
    border:1px solid rgba(0,212,255,.24);
    background:rgba(0,12,20,.9);
    transition:border-color .2s ease, box-shadow .2s ease;
  }
  #chatinput:focus {
    border-color:rgba(0,212,255,.7);
    box-shadow:0 0 22px rgba(0,212,255,.22);
  }
  .cbtn { transition:transform .15s ease, background .2s ease, box-shadow .2s ease; }
  .cbtn:hover { transform:translateY(-2px); }
  .cbtn:active { transform:translateY(0); }
```

- [ ] **Paso 4: Comprobar el conjunto**

Recargar y mirar el panel completo: los paneles deben verse más integrados, las cabeceras legibles de un vistazo y los botones con respuesta al pasar el ratón. Comprobar que arrastrar y redimensionar paneles sigue funcionando.

- [ ] **Paso 5: Commit**

```bash
git add app/static/index.html
git commit -m "feat: refinar el acabado visual del HUD"
```

---

### Tarea 9: Modo escucha ("Jarvis…" + 3 s de silencio)

**Ficheros:**
- Modificar: `app/static/index.html` (botón en la barra inferior, CSS del indicador, lógica nueva junto a la del micrófono)

**Interfaces:**
- Consume: `sendChat(text)` (definida en `index.html:1991`), que recibe el texto como argumento, lo pinta en la consola y vacía el input ella misma. También `log(texto, clase)` y el `#core-label` con la clase `speaking`.
- Produce: `modoEscucha` (bool) y `pararEscucha()`

Dos modos de voz que conviven: el botón de micrófono actual (pulsar y hablar) y el nuevo modo escucha. Se usa `webkitSpeechRecognition`, que Chromium trae de serie — sin dependencias ni coste.

Detalle importante: el reconocimiento **se para mientras JARVIS habla**, o se oiría a sí mismo y entraría en bucle.

- [ ] **Paso 1: Añadir el botón**

En la barra inferior, junto al del micrófono:

```html
      <button class="cbtn" id="btn-escucha" title="Modo escucha: di &quot;Jarvis…&quot; para hablarle">👂</button>
```

- [ ] **Paso 2: Indicador de que está escuchando**

```css
  /* Modo escucha: el boton se queda encendido y late suave */
  .cbtn.escuchando {
    background:rgba(0,255,179,.16);
    border-color:rgba(0,255,179,.6);
    color:#00ffb3;
    animation:escuchaPulso 2s ease-in-out infinite;
  }
  @keyframes escuchaPulso {
    0%, 100% { box-shadow:0 0 0 0 rgba(0,255,179,.35); }
    50%      { box-shadow:0 0 0 7px rgba(0,255,179,0); }
  }
  /* Cuando ya ha oido "Jarvis" y esta recogiendo la orden */
  .cbtn.captando {
    background:rgba(0,212,255,.2);
    border-color:#00d4ff; color:#00d4ff;
    animation:none;
  }
  @media (prefers-reduced-motion: reduce) { .cbtn.escuchando { animation:none; } }
```

- [ ] **Paso 3: La lógica**

Añadir junto al resto del código de voz:

```javascript
/* ============================================================ modo escucha
   Siempre atento, pero solo hace caso tras oir "Jarvis". A partir de ahi
   acumula lo que se dice y lo envia cuando pasan 3 segundos sin hablar.

   Usa el reconocimiento de voz de Chromium (va incluido en Electron): no
   añade dependencias y funciona sin llamar a ningun servicio externo. */
const PALABRAS_CLAVE = ['jarvis', 'yarvis', 'harvis'];  /* como suele oirlo */
const SILENCIO_MS = 3000;

let reconocedor = null;
let modoEscucha = false;
let captando = false;         /* ya se dijo "Jarvis": se recoge la orden */
let ordenParcial = '';
let temporizadorSilencio = null;

function soportaEscucha() {
  return 'webkitSpeechRecognition' in window || 'SpeechRecognition' in window;
}

function pintarEscucha() {
  const b = $('btn-escucha');
  b.classList.toggle('escuchando', modoEscucha && !captando);
  b.classList.toggle('captando', modoEscucha && captando);
}

function quitarClave(texto) {
  /* Se quita la palabra clave y lo que la precede: "oye jarvis que hora es"
     tiene que quedar en "que hora es". */
  const bajo = texto.toLowerCase();
  for (const c of PALABRAS_CLAVE) {
    const i = bajo.lastIndexOf(c);
    if (i !== -1) return texto.slice(i + c.length).replace(/^[\s,.:;]+/, '');
  }
  return texto;
}

function enviarOrden() {
  clearTimeout(temporizadorSilencio);
  const orden = ordenParcial.trim();
  ordenParcial = '';
  captando = false;
  pintarEscucha();
  if (!orden) return;
  sendChat(orden);            /* recibe el texto y limpia el input ella misma */
}

function iniciarEscucha() {
  if (!soportaEscucha()) {
    log('Este equipo no admite el modo escucha', 'warn');
    return false;
  }
  const Rec = window.SpeechRecognition || window.webkitSpeechRecognition;
  reconocedor = new Rec();
  reconocedor.lang = 'es-ES';
  reconocedor.continuous = true;
  reconocedor.interimResults = true;

  reconocedor.onresult = (ev) => {
    /* Mientras JARVIS habla no se hace caso: si no, se oye a si mismo. */
    if (document.getElementById('core-label').classList.contains('speaking')) return;

    let texto = '';
    for (let i = ev.resultIndex; i < ev.results.length; i++) {
      texto += ev.results[i][0].transcript;
    }
    const bajo = texto.toLowerCase();

    if (!captando) {
      if (!PALABRAS_CLAVE.some(c => bajo.includes(c))) return;
      captando = true;
      pintarEscucha();
      log('Escuchando…', 'ok');
    }
    ordenParcial = quitarClave(texto);

    /* Cada vez que se oye algo se reinicia la cuenta atras: la orden se
       manda cuando pasan 3 segundos completos en silencio. */
    clearTimeout(temporizadorSilencio);
    temporizadorSilencio = setTimeout(enviarOrden, SILENCIO_MS);
  };

  reconocedor.onerror = (ev) => {
    if (ev.error === 'no-speech' || ev.error === 'aborted') return;  /* normal */
    log('Error del microfono: ' + ev.error, 'bad');
    if (ev.error === 'not-allowed') pararEscucha();
  };

  /* El reconocedor se corta solo cada cierto tiempo: se relanza. */
  reconocedor.onend = () => { if (modoEscucha) { try { reconocedor.start(); } catch (e) {} } };

  try { reconocedor.start(); } catch (e) { return false; }
  return true;
}

function pararEscucha() {
  modoEscucha = false;
  captando = false;
  ordenParcial = '';
  clearTimeout(temporizadorSilencio);
  if (reconocedor) { reconocedor.onend = null; try { reconocedor.stop(); } catch (e) {} }
  reconocedor = null;
  pintarEscucha();
}

$('btn-escucha').addEventListener('click', () => {
  if (modoEscucha) {
    pararEscucha();
    log('Modo escucha desactivado', '');
    return;
  }
  modoEscucha = true;
  if (!iniciarEscucha()) { modoEscucha = false; }
  else log('Modo escucha activado. Di "Jarvis" y dime qué necesitas.', 'ok');
  pintarEscucha();
});

/* Al cerrar, soltar el microfono. */
addEventListener('beforeunload', pararEscucha);
```

- [ ] **Paso 4: Probarlo hablando**

Recargar, pulsar 👂 (el navegador pedirá permiso para el micrófono: aceptar). El botón debe quedarse verde latiendo. Decir *"Jarvis, cuánto es dos por dos"*, callarse, y a los 3 segundos debe enviarse la pregunta. Comprobar en la consola que aparece "Escuchando…" al oír la palabra clave.

Probar también que hablando **sin** decir "Jarvis" no se envía nada.

- [ ] **Paso 6: Comprobar que no se oye a sí mismo**

Con el modo escucha activo, mandar un mensaje por texto. Mientras JARVIS responde en voz alta, no debe activarse el modo captando ni enviarse nada.

- [ ] **Paso 7: Commit**

```bash
git add app/static/index.html
git commit -m "feat: modo escucha con palabra clave y envio por silencio"
```

---

### Tarea 10: Comprobación final y compilado

**Ficheros:**
- Ninguno nuevo

- [ ] **Paso 1: Comprobar la sintaxis**

```bash
venv\Scripts\python.exe -c "from app.main import app; from app import voice, services; print('backend OK')"
venv\Scripts\python.exe tests\test_voice_norm.py
venv\Scripts\python.exe tests\test_system_metrics.py
node -e "const h=require('fs').readFileSync('app/static/index.html','utf8');const m=h.match(/<script>([\s\S]*?)<\/script>/g)||[];for(const b of m){new Function(b.replace(/^<script>/,'').replace(/<\/script>$/,''))}console.log('frontend OK')"
```

Todos deben pasar.

- [ ] **Paso 2: Repaso completo en el panel**

Con `_dev.bat`, comprobar de una pasada:
- CPU / RAM / DISCO / UPTIME con valores
- Sin parpadeo del login al recargar
- El saludo suena solo, sin pulsar nada
- Sin botón de Estudio
- Consola grande y movible
- Ajustes con scroll y con velocidad y presets
- Núcleo con anillo, que late al hablar
- Modo escucha reaccionando a "Jarvis"

- [ ] **Paso 3: Compilar**

```bash
cd electron
npx electron-builder --win portable nsis
```

- [ ] **Paso 4: Probar el ejecutable**

Abrir `dist-electron\win-unpacked\J.A.R.V.I.S.exe` y repetir el repaso del paso 2 dentro de la app. Comprobar en `%APPDATA%\JARVIS\jarvis.log` que no hay errores.

- [ ] **Paso 5: Commit final**

```bash
git add -A
git commit -m "chore: comprobaciones y compilado de las mejoras de frontend"
git push
```

---

## Notas para quien lo ejecute

- **La codificación es delicada.** `index.html` y `main.js` han tenido problemas con los acentos. Guardar siempre en UTF-8 sin BOM y, tras editar, comprobar con `Select-String -Path <archivo> -Pattern "Ã|â€|Â"` que no aparece nada.
- **Los números de línea se mueven.** Los del plan son de referencia; buscar siempre por el texto o el selector, no por la línea.
- **Los `.bat` de prueba llevan `_` delante**, que ya está en `.gitignore`. Borrarlos al terminar.
- **Si Fish ignora la velocidad** (Tarea 6, paso 3), no forzarlo: quitar el parámetro, dejar dicho en el código que la API no lo admite y seguir. Los presets siguen valiendo para cambiar de voz.
- **Antes de dar algo por bueno, verlo funcionando.** El historial de este proyecto está lleno de cosas que "deberían funcionar" y no lo hacían.
