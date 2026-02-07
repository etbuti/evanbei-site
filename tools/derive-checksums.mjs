import fs from "node:fs";
import path from "node:path";
import crypto from "node:crypto";

function sha256File(absPath) {
  const buf = fs.readFileSync(absPath);
  return crypto.createHash("sha256").update(buf).digest("hex");
}

function exists(absPath) {
  try { fs.accessSync(absPath, fs.constants.F_OK); return true; } catch { return false; }
}

function ensureDir(absDir) {
  fs.mkdirSync(absDir, { recursive: true });
}

function utcNow() {
  return new Date().toISOString();
}

function normalizeWebPath(p) {
  // convert repo-relative path like ".well-known/node.json" -> "/.well-known/node.json"
  p = p.replace(/\\/g, "/").replace(/^\/+/, "");
  return "/" + p;
}

function main() {
  const repoRoot = process.cwd();

  // You can adjust this list anytime; keeping it small makes it stable/auditable.
  const targets = [
    "portal/portal.json",
    ".well-known/node.json",
    "well-known/node.json",     // optional/backup path
    "node/index.html",
    "node/health.html",
    "agent/manifest.json",      // if you added it
    "agent/capability-map.json" // if you added it
  ];

  const files = [];
  for (const rel of targets) {
    const abs = path.join(repoRoot, rel);
    if (!exists(abs)) continue; // tolerate optional files
    files.push({
      path: normalizeWebPath(rel),
      sha256: sha256File(abs)
    });
  }

  const outObj = {
    updated_utc: utcNow(),
    algo: "sha256",
    files
  };

  const outDir = path.join(repoRoot, "node");
  ensureDir(outDir);

  const outPath = path.join(outDir, "checksums.json");
  fs.writeFileSync(outPath, JSON.stringify(outObj, null, 2) + "\n", "utf8");

  console.log("✅ Generated node/checksums.json");
  console.log("   Entries:", files.length);
}

main();
