// Electron main process.
//
// Ρόλος:
//   1. Ξεκινά τον FastAPI backend (dev: τον τρέχει το `concurrently`· prod: τον
//      spawn-άρει εδώ ως subprocess από το bundled resource).
//   2. Περιμένει να απαντήσει το /health.
//   3. Φορτώνει το React UI (dev: Vite server· prod: το build στο dist/).
//
// CommonJS (.cjs) — το root package.json δεν έχει "type":"module".

const { app, BrowserWindow, shell } = require("electron");
const { spawn } = require("node:child_process");
const path = require("node:path");
const http = require("node:http");
const fs = require("node:fs");

const BACKEND_PORT = 8000;
const BACKEND_HOST = "127.0.0.1";
const HEALTH_URL = `http://${BACKEND_HOST}:${BACKEND_PORT}/health`;

// Στο dev, το concurrently τρέχει backend+frontend και θέτει ELECTRON_START_URL.
const START_URL = process.env.ELECTRON_START_URL; // π.χ. http://localhost:5173
const isDev = !!START_URL;

let backendProc = null;
let mainWindow = null;

// ── Backend lifecycle ─────────────────────────────────────────────────────────

function startBackend() {
  // Dev: ο backend τρέχει ήδη ξεχωριστά — μην τον ξεκινήσεις ξανά.
  if (isDev) return;

  const resources = process.resourcesPath; // .../resources μέσα στο packaged app
  const backendDir = path.join(resources, "backend");

  // Προτίμησε το PyInstaller-bundled exe· fallback σε system python + source.
  const exeName =
    process.platform === "win32" ? "prospectmatch-backend.exe" : "prospectmatch-backend";
  const exePath = path.join(backendDir, exeName);

  let cmd, args, cwd;
  if (fs.existsSync(exePath)) {
    cmd = exePath;
    args = ["--host", BACKEND_HOST, "--port", String(BACKEND_PORT)];
    cwd = backendDir;
  } else {
    // Fallback: system python + bundled source (απαιτεί deps — βλ. README)
    cmd = process.platform === "win32" ? "python" : "python3";
    args = ["run_server.py", "--host", BACKEND_HOST, "--port", String(BACKEND_PORT)];
    cwd = backendDir;
  }

  console.log(`[electron] starting backend: ${cmd} ${args.join(" ")}`);
  backendProc = spawn(cmd, args, { cwd, env: process.env });
  backendProc.stdout.on("data", (d) => process.stdout.write(`[backend] ${d}`));
  backendProc.stderr.on("data", (d) => process.stderr.write(`[backend] ${d}`));
  backendProc.on("exit", (code) => console.log(`[electron] backend exited: ${code}`));
}

function waitForHealth(timeoutMs = 60000) {
  const start = Date.now();
  return new Promise((resolve, reject) => {
    const poll = () => {
      http
        .get(HEALTH_URL, (res) => {
          if (res.statusCode === 200) {
            res.resume();
            resolve();
          } else {
            res.resume();
            retry();
          }
        })
        .on("error", retry);
    };
    const retry = () => {
      if (Date.now() - start > timeoutMs) {
        reject(new Error(`Backend health timeout (${HEALTH_URL})`));
      } else {
        setTimeout(poll, 400);
      }
    };
    poll();
  });
}

// ── Window ────────────────────────────────────────────────────────────────────

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 1000,
    minHeight: 640,
    backgroundColor: "#0e1117",
    title: "ProspectMatch",
    webPreferences: {
      preload: path.join(__dirname, "preload.cjs"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  // Άνοιγε external links στον default browser, όχι σε Electron window
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: "deny" };
  });

  if (isDev) {
    mainWindow.loadURL(START_URL);
    mainWindow.webContents.openDevTools({ mode: "detach" });
  } else {
    mainWindow.loadFile(path.join(__dirname, "..", "frontend", "dist", "index.html"));
  }

  mainWindow.on("closed", () => {
    mainWindow = null;
  });
}

// ── App lifecycle ─────────────────────────────────────────────────────────────

app.whenReady().then(async () => {
  startBackend();
  try {
    await waitForHealth();
  } catch (e) {
    console.error(`[electron] ${e.message}`);
    // Ανοίγουμε το παράθυρο ούτως ή άλλως — το UI δείχνει "Backend offline".
  }
  createWindow();

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});

// Σιγουρέψου ότι ο backend subprocess σκοτώνεται μαζί με το app.
app.on("quit", () => {
  if (backendProc && !backendProc.killed) {
    backendProc.kill();
  }
});
