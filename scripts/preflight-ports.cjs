#!/usr/bin/env node
/**
 * Preflight για το `npm run dev`.
 *
 * Ελευθερώνει τις πόρτες που χρειάζεται το dev stack (backend 8000, Vite 5173)
 * σκοτώνοντας ό,τι τις κρατά. Έτσι ένα ξεχασμένο uvicorn/vite/electron από
 * προηγούμενο run δεν μπλοκάρει το επόμενο (strictPort Vite + single-bind uvicorn).
 *
 * Τρέχει αυτόματα ως `predev` (npm hook). Cross-platform μέσω Node — χωρίς
 * εξάρτηση από shell syntax. Best-effort: αν μια πόρτα μείνει κατειλημμένη
 * παρά το kill, κάνει exit(1) με ξεκάθαρο μήνυμα αντί να αφήσει το dev να κρεμάσει.
 *
 * Override: `PROSPECTMATCH_NO_KILL=1 npm run dev` → μόνο report, χωρίς kill
 * (fail-fast αν κάτι τρέχει, ώστε να μην πειραχτεί κατά λάθος ξένη διεργασία).
 */

const { execSync } = require("node:child_process");
const net = require("node:net");

const PORTS = [8000, 5173];
const NO_KILL = process.env.PROSPECTMATCH_NO_KILL === "1";
const isWin = process.platform === "win32";

function sh(cmd) {
  try {
    return execSync(cmd, { stdio: ["ignore", "pipe", "ignore"] }).toString();
  } catch {
    return ""; // non-zero exit (π.χ. καμία αντιστοιχία) → κενό
  }
}

/** PIDs που ακούν (LISTEN) στη δοθείσα πόρτα. */
function pidsOnPort(port) {
  const pids = new Set();
  if (isWin) {
    // netstat -ano: γραμμές "  TCP  127.0.0.1:8000  ...  LISTENING  <pid>"
    const out = sh("netstat -ano -p TCP");
    for (const line of out.split(/\r?\n/)) {
      if (!/LISTENING/i.test(line)) continue;
      const cols = line.trim().split(/\s+/);
      const local = cols[1] || "";
      const pid = cols[cols.length - 1];
      if (local.endsWith(`:${port}`) && /^\d+$/.test(pid) && pid !== "0") {
        pids.add(pid);
      }
    }
  } else {
    // lsof: PIDs που ακούν στην πόρτα
    const out = sh(`lsof -nP -iTCP:${port} -sTCP:LISTEN -t`);
    for (const pid of out.split(/\r?\n/)) {
      if (/^\d+$/.test(pid.trim())) pids.add(pid.trim());
    }
  }
  return [...pids];
}

function killPid(pid) {
  if (isWin) sh(`taskkill /F /T /PID ${pid}`);
  else sh(`kill -9 ${pid}`);
}

/** Είναι η πόρτα ελεύθερη τώρα; (προσπάθεια bind) */
function isFree(port) {
  return new Promise((resolve) => {
    const srv = net.createServer();
    srv.once("error", () => resolve(false));
    srv.once("listening", () => srv.close(() => resolve(true)));
    // Δοκίμασε IPv4· αν το OS δώσει dual-stack, καλύπτει και ::1
    srv.listen(port, "0.0.0.0");
  });
}

async function main() {
  let stillBusy = false;

  for (const port of PORTS) {
    const pids = pidsOnPort(port);

    if (pids.length === 0) {
      console.log(`[preflight] port ${port}: free ✓`);
      continue;
    }

    if (NO_KILL) {
      console.error(
        `[preflight] port ${port}: κατειλημμένη από PID ${pids.join(", ")} ` +
          `(PROSPECTMATCH_NO_KILL=1 → δεν σκοτώνω). Ελευθέρωσέ την χειροκίνητα.`
      );
      stillBusy = true;
      continue;
    }

    console.log(`[preflight] port ${port}: busy (PID ${pids.join(", ")}) → freeing…`);
    for (const pid of pids) killPid(pid);
  }

  if (NO_KILL) {
    if (stillBusy) process.exit(1);
    return;
  }

  // Επιβεβαίωση ότι ελευθερώθηκαν (το kill μπορεί να αργήσει λίγο)
  for (const port of PORTS) {
    let free = false;
    for (let i = 0; i < 10; i++) {
      if (await isFree(port)) {
        free = true;
        break;
      }
      await new Promise((r) => setTimeout(r, 150));
    }
    if (!free) {
      console.error(
        `[preflight] ✗ port ${port} παραμένει κατειλημμένη. ` +
          `Κλείσ' την χειροκίνητα και ξανατρέξε:\n` +
          (isWin
            ? `    netstat -ano | findstr :${port}\n    taskkill /F /PID <pid>`
            : `    lsof -iTCP:${port} -sTCP:LISTEN\n    kill -9 <pid>`)
      );
      process.exit(1);
    }
  }

  console.log("[preflight] ports έτοιμες — starting dev stack.");
}

main();
