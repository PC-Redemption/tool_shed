#!/usr/bin/env node
"use strict";

// Dependency-free real-browser truth probe for the development qualification gate.
const childProcess = require("node:child_process");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");

function argumentsByName(argv) {
  const result = {};
  for (let index = 2; index < argv.length; index += 2) result[argv[index]] = argv[index + 1];
  return result;
}

function delay(milliseconds) {
  return new Promise((resolve) => setTimeout(resolve, milliseconds));
}

async function waitForFile(file, attempts = 200) {
  for (let attempt = 0; attempt < attempts; attempt += 1) {
    if (fs.existsSync(file)) return fs.readFileSync(file, "utf8").trim().split(/\r?\n/);
    await delay(50);
  }
  throw new Error("browser did not publish its DevTools endpoint");
}

class CDP {
  constructor(socket) {
    this.socket = socket;
    this.nextId = 1;
    this.pending = new Map();
    this.events = new Map();
    socket.addEventListener("message", (message) => {
      const payload = JSON.parse(message.data);
      if (payload.id && this.pending.has(payload.id)) {
        const entry = this.pending.get(payload.id);
        this.pending.delete(payload.id);
        if (payload.error) entry.reject(new Error(payload.error.message));
        else entry.resolve(payload.result || {});
      } else if (payload.method) {
        const waiters = this.events.get(payload.method) || [];
        this.events.delete(payload.method);
        for (const resolve of waiters) resolve(payload.params || {});
      }
    });
  }

  call(method, params = {}) {
    const id = this.nextId++;
    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject });
      this.socket.send(JSON.stringify({ id, method, params }));
    });
  }

  event(method) {
    return new Promise((resolve) => {
      const waiters = this.events.get(method) || [];
      waiters.push(resolve);
      this.events.set(method, waiters);
    });
  }
}

async function navigate(cdp, url) {
  const loaded = cdp.event("Page.loadEventFired");
  await cdp.call("Page.navigate", { url });
  await Promise.race([loaded, delay(10000).then(() => { throw new Error(`navigation timed out: ${url}`); })]);
  const location = await evaluate(cdp, "location.href");
  if (String(location).includes("/login/")) throw new Error(`authentication was lost while opening ${url}`);
  return location;
}

async function evaluate(cdp, expression) {
  const result = await cdp.call("Runtime.evaluate", { expression, returnByValue: true, awaitPromise: true });
  if (result.exceptionDetails) throw new Error(result.exceptionDetails.text || "browser evaluation failed");
  return result.result ? result.result.value : undefined;
}

async function main() {
  const args = argumentsByName(process.argv);
  const executable = args["--browser"];
  const baseUrl = String(args["--base-url"] || "").replace(/\/$/, "");
  const output = args["--output"];
  const username = process.env.TOOL_SHED_BROWSER_USERNAME;
  const password = process.env.TOOL_SHED_BROWSER_PASSWORD;
  if (!executable || !baseUrl || !output || !username || !password) {
    throw new Error("--browser, --base-url, --output and browser credential environment variables are required");
  }
  const userData = fs.mkdtempSync(path.join(os.tmpdir(), "tool-shed-browser-"));
  const browser = childProcess.spawn(executable, [
    "--headless=new", "--remote-debugging-port=0", `--user-data-dir=${userData}`,
    "--no-first-run", "--no-default-browser-check", "--disable-gpu", "--no-proxy-server",
    "about:blank",
  ], { stdio: "ignore", windowsHide: true });
  let cdp;
  try {
    const [port] = await waitForFile(path.join(userData, "DevToolsActivePort"));
    const target = await fetch(`http://127.0.0.1:${port}/json/new?about:blank`, { method: "PUT" }).then((response) => response.json());
    const socket = new WebSocket(target.webSocketDebuggerUrl);
    await new Promise((resolve, reject) => {
      socket.addEventListener("open", resolve, { once: true });
      socket.addEventListener("error", reject, { once: true });
    });
    cdp = new CDP(socket);
    await cdp.call("Page.enable");
    await cdp.call("Runtime.enable");
    const loginLoaded = cdp.event("Page.loadEventFired");
    await cdp.call("Page.navigate", { url: `${baseUrl}/dashboard/login/` });
    await loginLoaded;
    await evaluate(cdp, `(() => {
      const user = document.querySelector('input[name="username"]');
      const pass = document.querySelector('input[name="password"]');
      if (!user || !pass) throw new Error('login form missing');
      user.value = ${JSON.stringify(username)};
      pass.value = ${JSON.stringify(password)};
      user.form.requestSubmit();
      return true;
    })()`);
    await delay(500);
    await navigate(cdp, `${baseUrl}/dashboard/`);
    const overview = await evaluate(cdp, `(() => ({
      development: document.body.dataset.dashboardEnvironment === 'development' || !!document.querySelector('.dashboard-environment-banner'),
      rows: [...document.querySelectorAll('.compact-table-panel tbody tr')].map((row) => ({
        name: row.querySelector('th a')?.textContent.trim() || '',
        href: row.querySelector('th a')?.getAttribute('href') || '',
        attention_state: row.querySelector('.state-badge')?.textContent.trim().toLowerCase() || 'unknown'
      })).filter((row) => row.name)
    }))()`);
    const projects = [];
    let linksOk = true;
    for (const row of overview.rows) {
      const projectUrl = new URL(row.href, baseUrl).toString();
      await navigate(cdp, projectUrl);
      const summaryState = await evaluate(cdp, "document.querySelector('.project-summary-bar .state-badge')?.textContent.trim().toLowerCase() || 'unknown'");
      const workUrl = new URL(`${row.href.replace(/\/$/, "")}/work/?rows=all`, baseUrl).toString();
      await navigate(cdp, workUrl);
      const work = await evaluate(cdp, `(() => ({
        ids: [...document.querySelectorAll('.work-table .artifact-id')].map((node) => node.textContent.trim()),
        rows: [...document.querySelectorAll('.work-table tbody tr')].map((node) => node.textContent.replace(/\s+/g, ' ').trim())
      }))()`);
      for (const tab of ["outcomes", "health"]) {
        const targetUrl = new URL(`${row.href.replace(/\/$/, "")}/${tab}/`, baseUrl).toString();
        try { await navigate(cdp, targetUrl); } catch (error) { linksOk = false; }
      }
      projects.push({
        name: row.name,
        href: row.href,
        attention_state: summaryState,
        freshness: summaryState === "stale" ? "stale" : "fresh",
        work_artifact_ids: work.ids,
        work_rows: work.rows,
      });
    }
    const payload = {
      schema_version: 1,
      kind: "tool-shed-dashboard-browser-snapshot",
      source: { layer: "real-browser", authority_class: "presentation", browser: path.basename(executable) },
      base_url: baseUrl,
      development_banner: overview.development,
      project_names: overview.rows.map((row) => row.name),
      projects,
      links_ok: linksOk,
    };
    fs.mkdirSync(path.dirname(path.resolve(output)), { recursive: true });
    fs.writeFileSync(output, `${JSON.stringify(payload, null, 2)}\n`, "utf8");
    process.stdout.write(`${JSON.stringify(payload, null, 2)}\n`);
    await cdp.call("Browser.close").catch(() => {});
  } finally {
    if (!browser.killed) browser.kill();
    fs.rmSync(userData, { recursive: true, force: true });
  }
}

main().catch((error) => {
  process.stderr.write(`Dashboard browser probe failed: ${error.message}\n`);
  process.exitCode = 2;
});
