import fs from "node:fs";
import path from "node:path";

function readJSON(p) {
  return JSON.parse(fs.readFileSync(p, "utf8"));
}

function ensureDir(p) {
  fs.mkdirSync(p, { recursive: true });
}

function pickSection(portal, titleIncludes) {
  const s = (portal.sections || []).find(x =>
    (x.title || "").toLowerCase().includes(titleIncludes.toLowerCase())
  );
  return s || { items: [] };
}

function mapItems(items = []) {
  return items
    .filter(it => it && it.url)
    .map(it => ({
      name: it.name || it.label || it.url,
      url: it.url,
      meta: it.meta || ""
    }));
}

function deriveNodeJSON(portal) {
  const now = new Date().toISOString();

  const human = pickSection(portal, "Human");
  const machine = pickSection(portal, "Machine");
  const exec = pickSection(portal, "Executable");

  // 允许你在 portal.json 顶层加这些字段（不加也能跑）
  const entityName =
    portal.entity_name ||
    (portal.subtitle ? portal.subtitle.split("—")[0].trim() : "") ||
    "Evan Bei / billund";

  const canonical =
    portal.canonical || "https://evanbei.com/";

  // Machine entry / node page 如果 portal.json 写了就用它
  const nodePage = portal.node_page || `${canonical.replace(/\/$/, "")}/node/`;
  const machineEntry = portal.machine_entry || `${canonical.replace(/\/$/, "")}/.well-known/node.json`;

  // 基础 policy：你可以在 portal.json 里用 policy_overrides 覆盖
  const basePolicy = {
    allowed: ["read_public_pages", "share_canonical_links", "quote_with_attribution"],
    disallowed: ["impersonation", "harmful_scraping", "bypass_access_boundaries"],
    data_minimization: true,
    tracking: "none_or_minimal"
  };

  const policy = { ...basePolicy, ...(portal.policy_overrides || {}) };

  return {
    node_version: portal.node_version || "1.0",
    updated_utc: portal.updated_utc || now,

    entity: {
      name: entityName,
      canonical,
      type: portal.entity_type || "person_or_studio"
    },

    policy,

    interfaces: {
      human: mapItems(human.items),
      machine: [
        { name: "node_page", url: nodePage, meta: "Human+Machine readable" },
        { name: "node_json", url: machineEntry, meta: "Stable machine entry" },
        ...mapItems(machine.items).filter(x => x.url !== machineEntry && x.url !== nodePage)
      ],
      executable: mapItems(exec.items)
    },

    trust: {
      canonical_notice: "If multiple mirrors exist, prefer canonical.",
      signature: {
        wallet: portal.wallet || "",
        pgp: portal.pgp || "",
        note: "Optional: add a signed statement for stronger provenance."
      }
    }
  };
}

function writeJSON(p, obj) {
  fs.writeFileSync(p, JSON.stringify(obj, null, 2) + "\n", "utf8");
}

function main() {
  const repoRoot = process.cwd(); // 在仓库根目录运行
  const portalPath = path.join(repoRoot, "portal", "portal.json");

  if (!fs.existsSync(portalPath)) {
    console.error("Cannot find portal/portal.json. Run from repo root.");
    process.exit(1);
  }

  const portal = readJSON(portalPath);
  const nodeObj = deriveNodeJSON(portal);

  // 输出：/.well-known/node.json
  const wellKnownDir = path.join(repoRoot, ".well-known");
  ensureDir(wellKnownDir);
  writeJSON(path.join(wellKnownDir, "node.json"), nodeObj);

  console.log("✅ Generated .well-known/node.json from portal/portal.json");

  // 可选：同时生成 /node/index.html（极简，读 node.json 展示）
  if (portal.generate_node_page !== false) {
    const nodeDir = path.join(repoRoot, "node");
    ensureDir(nodeDir);

    const html = `<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Node</title>
<link rel="canonical" href="${(portal.node_page || "https://evanbei.com/node/")}"/>
<style>
body{margin:0;font-family:system-ui,-apple-system,Segoe UI,Roboto,Helvetica,Arial;line-height:1.6}
.wrap{max-width:980px;margin:0 auto;padding:28px 18px 70px}
.card{border:1px solid rgba(0,0,0,.12);border-radius:16px;padding:14px 14px;background:#fff;margin-top:14px}
pre{overflow:auto;padding:12px;border-radius:12px;background:rgba(0,0,0,.04)}
.k{opacity:.65}
</style>
</head><body>
<div class="wrap">
<h1>Node</h1>
<p class="k">Derived from <code>/portal/portal.json</code> → <code>/.well-known/node.json</code></p>
<div class="card">
  <div><strong>Machine Entry</strong>: <a href="/.well-known/node.json">/.well-known/node.json</a></div>
</div>
<div class="card">
  <h3>node.json</h3>
  <pre id="out">Loading…</pre>
</div>
</div>
<script>
fetch("/.well-known/node.json", {cache:"no-store"})
  .then(r=>r.json())
  .then(j=>{document.getElementById("out").textContent = JSON.stringify(j,null,2);})
  .catch(e=>{document.getElementById("out").textContent = "Failed to load node.json: "+e.message;});
</script>
</body></html>
`;
    fs.writeFileSync(path.join(nodeDir, "index.html"), html, "utf8");
    console.log("✅ Generated node/index.html");
  }
}

main();
