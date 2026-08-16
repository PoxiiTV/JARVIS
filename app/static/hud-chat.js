let pendingAudio = null;
let audioVoz = null;
let colaVoz = [];
let vozPendiente = false;
let enKiosco = false;
let bootStep = 0, bootTimer = null, bootEl = null, ttsFailed = false;

/* Estado "hablando": reactor 3D + etiqueta del núcleo (sin texto centrado) */
function setSpeaking(v) {
  speaking = v;
  const lbl = $('core-label');
  if (lbl) {
    lbl.textContent = v ? '▮▮' : 'JARVIS';
    lbl.classList.toggle('speaking', v);
  }
  mandarPausaEscucha(!!v);
}

function cortarVoz() {
  colaVoz = [];
  vozPendiente = false;
  const a = audioVoz;
  audioVoz = null;
  if (!a) {
    if (speaking) setSpeaking(false);
    return;
  }
  try {
    a.onended = null;
    a.onerror = null;
    a.pause();
    a.removeAttribute('src');
    a.load();
  } catch (e) {}
  setSpeaking(false);
}
function playAudio(a) {
  const prev = audioVoz;
  if (prev && prev !== a) {
    try {
      prev.onended = null;
      prev.onerror = null;
      prev.pause();
      prev.removeAttribute('src');
      prev.load();
    } catch (e) {}
  }
  audioVoz = a;
  setSpeaking(true);
  const ended = a.onended;
  const err = a.onerror;
  a.onended = () => {
    if (audioVoz === a) audioVoz = null;
    if (typeof ended === 'function') ended.call(a);
    if (!audioVoz && !vozPendiente) setSpeaking(false);
  };
  a.onerror = () => {
    if (audioVoz === a) audioVoz = null;
    setSpeaking(false);
    if (typeof err === 'function') err.call(a);
  };
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
function speak(text) {
  if (muted) return;
  const t = String(text || '').trim();
  if (!t) return;
  if (audioVoz || vozPendiente) {
    colaVoz.push(t);
    return;
  }
  vozPendiente = true;
  setSpeaking(true);
  api('/api/tts', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({text: t}) })
    .then(r => r.blob())
    .then(blob => {
      vozPendiente = false;
      const a = new Audio(URL.createObjectURL(blob));
      a.onended = () => {
        const next = colaVoz.shift();
        if (next) speak(next);
      };
      a.onerror = () => { setSpeaking(false); log('Error de audio', 'bad'); };
      playAudio(a);
    })
    .catch(e => { vozPendiente = false; setSpeaking(false); log('Error de voz: ' + e.message, 'bad'); });
}

/* ============================================================ pulso de "te oí" (sin voz) */
function playAck() {
  const hud = document.getElementById('hud-ui');
  if (!hud) return;
  hud.classList.remove('ack-pulse');
  void hud.offsetWidth;
  hud.classList.add('ack-pulse');
  setTimeout(() => hud.classList.remove('ack-pulse'), 700);
}
function cancelAck() {
  const hud = document.getElementById('hud-ui');
  if (hud) hud.classList.remove('ack-pulse');
}

/* ============================================================ chat */
function textoSinEmocion(t) {
  /* Quita [calm] [happy]... de la consola: son para Fish, no para leer. */
  let s = String(t || '');
  const marca = /The model produced only internal reasoning/i;
  if (marca.test(s)) {
    const corte = s.match(/which may contain the(?:\s+answer)?:\s*/i);
    if (corte) s = s.slice(s.indexOf(corte[0]) + corte[0].length);
  }
  s = s.replace(/^[\s⚠️⚠]+/, '');
  s = s.replace(/`/g, '').replace(/~/g, '');
  s = s.replace(/\*\*/g, '').replace(/\*/g, '');
  return s.replace(/\[[a-z][a-z0-9 -]{0,40}\]\s*/gi, '').trim();
}
function fraseEnEllo(seg, estado) {
  return 'JARVIS: ' + (estado || 'En ello, señor.');
}
function pintarPensando(v) {
  const hud = document.getElementById('hud-ui');
  if (hud) hud.classList.toggle('thinking', !!v);
}
function pintarRecibo(d) {
  const el = $('v-recibo');
  if (!el) return;
  el.textContent = (d.ok ? '' : 'Fallo: ') + (d.detail || d.tool || '—');
  el.className = d.ok ? 'ok' : 'bad';
  log((d.ok ? 'Recibo: ' : 'Recibo fallido: ') + (d.detail || ''), d.ok ? 'ok' : 'bad');
}
function pintarMision(maquina, mision) {
  const vm = $('v-maquina');
  const vs = $('v-mision');
  if (vm && maquina != null) vm.textContent = maquina;
  if (vs && mision != null) vs.textContent = mision;
  const hud = document.getElementById('hud-ui');
  if (hud && maquina != null) hud.classList.toggle('remote', maquina === 'portátil');
}
function tickSiCambia(el, clave, ahora) {
  if (!el) return;
  const prev = tickSiCambia._prev || (tickSiCambia._prev = {});
  if (prev[clave] !== undefined && prev[clave] !== ahora) {
    el.classList.remove('tick');
    void el.offsetWidth;
    el.classList.add('tick');
    setTimeout(() => el.classList.remove('tick'), 600);
  }
  prev[clave] = ahora;
}
function pideVision(text) {
  const t = (text || '').toLowerCase();
  return /qu[eé]\s+ves|mira(?:\s+la)?\s+c[aá]mara|describe\s+lo\s+que|qu[eé]\s+tengo\s+delante|qu[eé]\s+hay\s+ah[ií]/.test(t);
}
async function capturarFrame() {
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) return null;
  const stream = await navigator.mediaDevices.getUserMedia({ video: { width: 640 } });
  const v = document.createElement('video');
  v.srcObject = stream;
  await v.play();
  await new Promise(r => setTimeout(r, 300));
  const c = document.createElement('canvas');
  c.width = 640;
  c.height = 480;
  c.getContext('2d').drawImage(v, 0, 0, 640, 480);
  stream.getTracks().forEach(t => t.stop());
  const blob = await new Promise(r => c.toBlob(r, 'image/jpeg', 0.8));
  const fd = new FormData();
  fd.append('image', blob, 'cam.jpg');
  fd.append('question', 'Describe qué ves. Responde en español, breve.');
  const r = await apiJSON('/api/vision', { method: 'POST', body: fd }).catch(() => null);
  return (r && r.description) || null;
}
async function sendChat(text, voz) {
  if (!text || sendChat._busy) return;
  if (pideVision(text)) {
    const desc = await capturarFrame().catch(() => null);
    if (!desc) {
      log('No veo la cámara.', 'warn');
      speak('[calm] No veo la cámara.');
      return;
    }
    text = 'El señor pregunta: ' + text + '. La cámara ve: ' + desc;
  }
  sendChat._busy = true;
  sendChat._spokeHead = false;
  sendChat._head = '';
  cortarVoz();
  if (narrow() && window.switchMobileTab) window.switchMobileTab('chat');
  log('Tú: ' + text, '');
  $('chatinput').value = '';
  playAck();
  pintarMision('este PC', 'recibida');
  let estado = 'En ello, señor.';
  let hayTexto = false;
  pintarPensando(true);
  const vivo = log(fraseEnEllo(0, estado), 'warn');
  try {
    const r = await api('/api/chat/stream', {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify({text, voice: !!voz})
    });
    if (!r.body) throw new Error('sin stream');
    const reader = r.body.getReader();
    const dec = new TextDecoder();
    let buf = '';
    let last = {};
    while (true) {
      const chunk = await reader.read();
      if (chunk.done) break;
      buf += dec.decode(chunk.value, {stream: true});
      const lines = buf.split('\n');
      buf = lines.pop();
      for (const line of lines) {
        if (!line.trim()) continue;
        let d;
        try { d = JSON.parse(line); } catch (e) { continue; }
        if (d.t === 'status' && d.msg && !hayTexto) {
          estado = d.msg;
          vivo.textContent = '> ' + fraseEnEllo(0, estado);
          if (/hermes|portátil/i.test(d.msg)) pintarMision('portátil', d.msg);
          else pintarMision(null, d.msg);
        }
        if (d.t === 'text' && (d.reply || '').trim()) {
          hayTexto = true;
          pintarPensando(false);
          vivo.className = 'ok';
          vivo.textContent = '> JARVIS: ' + textoSinEmocion(d.reply);
          logEl.scrollTop = logEl.scrollHeight;
          if (voz && !sendChat._spokeHead) {
            const m = d.reply.match(/^(.{15,}?[.!?…])(\s|$)/);
            if (m) {
              sendChat._spokeHead = true;
              sendChat._head = m[1];
              speak(m[1]);
            }
          }
        }
        if (d.t === 'receipt') pintarRecibo(d);
        if (d.t === 'done') last = d;
      }
    }
    cancelAck();
    if (last.error && !(last.reply || '').trim()) {
      vivo.className = 'bad';
      vivo.textContent = '> Error del cerebro: ' + last.error;
      pintarMision(null, 'fallo');
    } else if ((last.reply || '').trim()) {
      hayTexto = true;
      pintarPensando(false);
      pintarMision(null, 'completa');
      vivo.className = 'ok';
      vivo.textContent = '> JARVIS: ' + textoSinEmocion(last.reply);
      if (sendChat._spokeHead) {
        const rest = last.reply.slice(sendChat._head.length).trim();
        if (rest) speak(rest);
      } else {
        speak(last.reply);
      }
    } else if (!hayTexto) {
      vivo.className = 'bad';
      vivo.textContent = '> Error del cerebro: sin texto';
      pintarMision(null, 'fallo');
    } else if (!sendChat._spokeHead) {
      pintarMision(null, 'completa');
      speak(vivo.textContent.replace(/^> JARVIS:\s*/, ''));
    } else {
      pintarMision(null, 'completa');
    }
  } catch (e) {
    vivo.className = 'bad';
    vivo.textContent = '> Error del cerebro: ' + (e && e.message ? e.message : 'sin red');
    pintarMision(null, 'fallo');
  } finally {
    pintarPensando(false);
    sendChat._busy = false;
  }
}
