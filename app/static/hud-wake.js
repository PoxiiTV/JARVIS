/* ============================================================ modo escucha
   El oído local espera la palabra clave. Whisper y el cerebro
   solo entran UNA vez, cuando ya te ha llamado. */
let modoEscucha = false;
let captando = false;
let escuchaStream = null;
let escuchaCtx = null;
let escuchaAnalyser = null;
let escuchaProc = null;
let escuchaWs = null;
let escuchaGen = 0;
let vuTimer = null;
let escuchaPausa = false;

function jarvisHabla() {
  const lbl = document.getElementById('core-label');
  return !!(lbl && lbl.classList.contains('speaking'));
}

function pintarEscucha() {
  const b = $('btn-escucha');
  b.classList.toggle('escuchando', modoEscucha && !captando);
  b.classList.toggle('captando', modoEscucha && captando);
}

function rmsEscucha() {
  if (!escuchaAnalyser) return 0;
  const data = new Uint8Array(escuchaAnalyser.fftSize);
  escuchaAnalyser.getByteTimeDomainData(data);
  let sum = 0;
  for (let i = 0; i < data.length; i++) {
    const v = (data[i] - 128) / 128;
    sum += v * v;
  }
  return Math.sqrt(sum / data.length);
}

function arrancarVu() {
  clearInterval(vuTimer);
  vuTimer = setInterval(() => {
    if (!modoEscucha) {
      clearInterval(vuTimer);
      vuTimer = null;
      if (!recording) setMicStatus('');
      return;
    }
    if (recording) return;
    const rms = rmsEscucha();
    const n = Math.min(10, Math.round(rms * 70));
    const barras = n > 0 ? '█'.repeat(n) : '·';
    setMicStatus((captando ? '👂 Te escucho ' : '👂 JARVIS ') + barras);
  }, 120);
}

function floatAPcm16k(float32, inRate) {
  const ratio = inRate / 16000;
  const n = Math.floor(float32.length / ratio);
  const out = new Int16Array(n);
  for (let i = 0; i < n; i++) {
    const s = Math.max(-1, Math.min(1, float32[Math.floor(i * ratio)] || 0));
    out[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
  }
  return out;
}

const BARGE_RMS = 0.02;
function rmsDe(buf) {
  let s = 0;
  for (let i = 0; i < buf.length; i++) s += buf[i] * buf[i];
  return Math.sqrt(s / buf.length);
}

function mandarPausaEscucha(v) {
  if (escuchaPausa === v) return;
  escuchaPausa = v;
  if (escuchaWs && escuchaWs.readyState === 1) {
    try { escuchaWs.send(JSON.stringify({ pause: !!v })); } catch (e) {}
  }
}

async function iniciarEscucha(ctx) {
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    log('Microfono no disponible', 'warn');
    return false;
  }
  try {
    escuchaStream = await abrirMicro();
  } catch (e) {
    log('Microfono denegado: ' + e.message, 'bad');
    return false;
  }
  const pista = escuchaStream.getAudioTracks()[0];
  if (pista && pista.readyState !== 'live') {
    log('El micro no está activo (' + (pista.readyState || 'apagado') + ')', 'bad');
    return false;
  }
  escuchaCtx = ctx || new (window.AudioContext || window.webkitAudioContext)();
  if (escuchaCtx.state === 'suspended') {
    try { await escuchaCtx.resume(); } catch (e) {}
  }
  const src = escuchaCtx.createMediaStreamSource(escuchaStream);
  escuchaAnalyser = escuchaCtx.createAnalyser();
  escuchaAnalyser.fftSize = 2048;
  src.connect(escuchaAnalyser);
  const silencio = escuchaCtx.createGain();
  silencio.gain.value = 0;
  escuchaProc = escuchaCtx.createScriptProcessor(4096, 1, 1);
  escuchaAnalyser.connect(escuchaProc);
  escuchaProc.connect(silencio);
  silencio.connect(escuchaCtx.destination);

  const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
  const ws = new WebSocket(proto + '//' + location.host + '/api/wake');
  escuchaWs = ws;
  escuchaPausa = false;
  ws.binaryType = 'arraybuffer';
  const gen = ++escuchaGen;
  ws.onmessage = ev => {
    if (gen !== escuchaGen) return;
    let d;
    try { d = JSON.parse(ev.data); } catch (e) { return; }
    if (d.event === 'loading') log(d.text || 'Preparando oído…', '');
    if (d.event === 'ready') log('Atento a JARVIS. El cerebro descansa hasta que me llames.', 'ok');
    if (d.event === 'wake') {
      cortarVoz();
      captando = true;
      pintarEscucha();
      playAck();
      log('Te escucho…', 'ok');
    }
    if (d.event === 'order' && d.text) {
      captando = false;
      pintarEscucha();
      sendChat(d.text, true);
    }
    if (d.event === 'timeout') {
      captando = false;
      pintarEscucha();
      log('Te oí, pero no la orden. Di JARVIS y lo que necesitas.', 'warn');
    }
    if (d.event === 'error') log('Oído: ' + (d.text || 'error'), 'bad');
  };
  try {
    await new Promise((resolve, reject) => {
      ws.addEventListener('open', resolve, { once: true });
      ws.addEventListener('error', () => reject(new Error('No conectó el oído local')), { once: true });
      setTimeout(() => reject(new Error('timeout oído')), 8000);
    });
  } catch (e) {
    log(e.message, 'bad');
    return false;
  }

  escuchaProc.onaudioprocess = e => {
    if (!modoEscucha || gen !== escuchaGen) return;
    if (recording) {
      mandarPausaEscucha(true);
      return;
    }
    const samples = e.inputBuffer.getChannelData(0);
    if (speaking && rmsDe(samples) > BARGE_RMS) {
      cortarVoz();
    }
    if (speaking) {
      mandarPausaEscucha(true);
      return;
    }
    mandarPausaEscucha(false);
    if (ws.readyState !== 1) return;
    const pcm = floatAPcm16k(samples, escuchaCtx.sampleRate);
    if (pcm.length) ws.send(pcm.buffer);
  };

  modoEscucha = true;
  log('Escuchando por: ' + nombreMicro(escuchaStream), 'ok');
  return true;
}

function pararEscucha() {
  escuchaGen++;
  modoEscucha = false;
  captando = false;
  escuchaPausa = false;
  clearInterval(vuTimer);
  vuTimer = null;
  if (!recording) setMicStatus('');
  if (escuchaProc) {
    try { escuchaProc.disconnect(); } catch (e) {}
    escuchaProc.onaudioprocess = null;
    escuchaProc = null;
  }
  if (escuchaWs) {
    try { escuchaWs.close(); } catch (e) {}
    escuchaWs = null;
  }
  if (escuchaStream) {
    escuchaStream.getTracks().forEach(t => t.stop());
    escuchaStream = null;
  }
  if (escuchaCtx) {
    escuchaCtx.close().catch(() => {});
    escuchaCtx = null;
  }
  escuchaAnalyser = null;
  pintarEscucha();
}

let escuchaArrancando = false;

async function activarEscucha() {
  if (modoEscucha || escuchaArrancando) return;
  escuchaArrancando = true;
  const Ctx = window.AudioContext || window.webkitAudioContext;
  const ctx = new Ctx();
  try { if (ctx.state === 'suspended') await ctx.resume(); } catch (e) {}
  try {
    if (!(await iniciarEscucha(ctx))) {
      try { ctx.close(); } catch (e) {}
      pararEscucha();
      return;
    }
    log('Di «JARVIS» y la orden. Primera vez puede tardar en bajar el oído.', 'ok');
    pintarEscucha();
    arrancarVu();
  } finally {
    escuchaArrancando = false;
  }
}
