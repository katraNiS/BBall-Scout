// Preload — τρέχει με context isolation πριν φορτώσει το renderer.
// Ελάχιστο surface: εκθέτουμε μόνο app metadata. Ο backend είναι HTTP (localhost),
// οπότε δεν χρειάζεται IPC bridge για τα δεδομένα.

const { contextBridge } = require("electron");

contextBridge.exposeInMainWorld("prospectmatch", {
  platform: process.platform,
  isElectron: true,
  backendBase: "http://127.0.0.1:8000",
});
