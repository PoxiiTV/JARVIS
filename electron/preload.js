/**
 * Puente entre el tutorial y el proceso principal.
 *
 * La ventana va con contextIsolation, así que el tutorial no tiene Node: solo
 * puede llamar a lo que se expone aquí. Cada función es una acción concreta,
 * nada de dar acceso genérico al sistema de archivos ni a ipcRenderer.
 */
const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('jarvis', {
  guardarConfig: (datos) => ipcRenderer.invoke('tutorial:guardar', datos),
  instalar: () => ipcRenderer.invoke('tutorial:instalar'),
  probarVoz: (opts) => ipcRenderer.invoke('tutorial:probar-voz', opts),
  abrirEnlace: (url) => ipcRenderer.invoke('tutorial:abrir-enlace', url),
  terminar: () => ipcRenderer.invoke('tutorial:terminar'),
  saltar: () => ipcRenderer.invoke('tutorial:saltar'),

  /** Progreso de la instalación: {tareas, linea, porcentaje, indeterminado} */
  alProgreso: (fn) => ipcRenderer.on('tutorial:progreso', (_e, d) => fn(d)),
});
