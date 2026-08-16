# Personalidades por voz — Plan

> **For agentic workers:** Use executing-plans. TDD. No commit hasta que lo pida el señor.

**Goal:** El tono del turno sigue al chip de voz (Fermín entero). Acciones, verdad y recibos no cambian. Más personajes = un `.md` + alias en el mapa.

**Architecture:** El HUD manda `VOZ_NOMBRE` al aplicar el chip. `app/personalidad.py` resuelve slug por alias (subcadena con bordes de palabra). Si hay `personalidades/<slug>.md`, `_mensajes_base` inyecta un system extra que pisa el tono de mayordomo, no las tools. Briefing hablado se adapta si el slug tiene saludo.

**Tech Stack:** Python stdlib · FastAPI ajustes ya existentes · chips de voz en `index.html`

---

## Archivos

- Create: `personalidades/mapa.json`, `personalidades/fermin.md`, `app/personalidad.py`, `tests/test_personalidad.py`
- Modify: `app/config.py`, `app/main.py`, `app/brain.py`, `app/briefing.py`, `app/static/index.html`, `tests/test_briefing.py`, `tests/run_iron.bat`, `README.md`

No tocar router Hermes, recibos, Spotify, Tuya.

---

### Task 1: Resolver slug por nombre del chip

**Files:** Create `tests/test_personalidad.py`, `app/personalidad.py`, `personalidades/mapa.json`

- [ ] Test: `slug_de("Fermín Trujillo") == "fermin"`; `slug_de("JARVIS") is None`
- [ ] Implementar `_norm` + mapa + `slug_de`
- [ ] Commit: no (el señor no lo ha pedido)

### Task 2: Bloque de sistema + inyección

- [ ] Test: bloque de Fermín cita estilo y dice que no pisa VERDAD/tools
- [ ] Test: `_mensajes_base` incluye el bloque si `Config.VOZ_NOMBRE` es Fermín; no si es JARVIS
- [ ] `bloque(nombre)` lee `personalidades/<slug>.md`
- [ ] `_mensajes_base` inserta tras `SYSTEM_PROMPT`

### Task 3: Ajustes + HUD

- [ ] `Config.VOZ_NOMBRE`, `AJUSTES_EDITABLES`, hot-reload, cap 80, sin saltos
- [ ] `aplicarVoz` POST `{ FISH_VOICE_ID, FISH_VOLUME, VOZ_NOMBRE }`
- [ ] Ocultar `VOZ_NOMBRE` en el formulario (como `FISH_VOICE_ID`)

### Task 4: Briefing

- [ ] Fermín: «Buenos días, tío.» + mismos datos; JARVIS sin cambio
- [ ] `texto_briefing` usa `Config.VOZ_NOMBRE`

### Task 5: Verificar

- [ ] `tests\run_iron.bat` + `tests\test_personalidad.py`
