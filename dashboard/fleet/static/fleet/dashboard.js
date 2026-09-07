document.addEventListener("DOMContentLoaded", () => {
  const viewerTimeZone = Intl.DateTimeFormat().resolvedOptions().timeZone;
  const localDateTime = new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: viewerTimeZone,
  });
  const localDate = new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeZone: viewerTimeZone,
  });
  const localClock = new Intl.DateTimeFormat(undefined, {
    timeStyle: "short",
    timeZone: viewerTimeZone,
  });
  document.querySelectorAll("time[data-local-time]").forEach((element) => {
    const instant = new Date(element.dateTime);
    if (Number.isNaN(instant.getTime())) return;
    const datePart = element.querySelector("[data-local-date]");
    const clockPart = element.querySelector("[data-local-clock]");
    if (datePart && clockPart) {
      datePart.textContent = localDate.format(instant);
      clockPart.textContent = localClock.format(instant);
    } else {
      element.textContent = localDateTime.format(instant);
    }
    element.title = `${localDateTime.format(instant)} (${viewerTimeZone || "browser local time"})`;
  });

  document.querySelectorAll("[data-auto-submit]").forEach((control) => {
    control.addEventListener("change", () => {
      if (!control.form) return;
      control.form.requestSubmit();
    });
  });

  document.querySelectorAll("[data-copy-command]").forEach((button) => {
    button.addEventListener("click", async () => {
      const command = button.dataset.copyCommand || "";
      const feedback = button.closest(".artifact-command-menu, .local-command")?.querySelector(".copy-feedback");
      let copied = false;
      try {
        if (navigator.clipboard?.writeText) {
          await navigator.clipboard.writeText(command);
          copied = true;
        }
      } catch (_error) {
        copied = false;
      }
      if (!copied) {
        const field = document.createElement("textarea");
        field.value = command;
        field.setAttribute("readonly", "");
        field.style.position = "fixed";
        field.style.opacity = "0";
        document.body.appendChild(field);
        field.select();
        copied = document.execCommand("copy");
        field.remove();
      }
      if (feedback) {
        feedback.textContent = copied
          ? button.dataset.copyFeedback || "Command copied"
          : "Clipboard unavailable; select and copy the command shown.";
      }
    });
  });

  const treeRows = Array.from(document.querySelectorAll("[data-tree-row]"));
  const treeDepthControls = Array.from(document.querySelectorAll("[data-tree-depth-control]"));
  const treeRowsByParent = new Map();
  treeRows.forEach((row) => {
    const parent = row.dataset.treeParent || "";
    if (!treeRowsByParent.has(parent)) treeRowsByParent.set(parent, []);
    treeRowsByParent.get(parent).push(row);
  });
  const setDescendantsHidden = (parentId, hidden) => {
    (treeRowsByParent.get(parentId) || []).forEach((row) => {
      row.hidden = hidden;
      if (hidden) {
        setDescendantsHidden(row.dataset.treeId || "", true);
        return;
      }
      const childToggle = row.querySelector("[data-tree-toggle]");
      if (!childToggle || childToggle.getAttribute("aria-expanded") === "true") {
        setDescendantsHidden(row.dataset.treeId || "", false);
      }
    });
  };
  const setTreeToggleExpanded = (toggle, expanded) => {
    toggle.setAttribute("aria-expanded", String(expanded));
    toggle.setAttribute(
      "aria-label",
      `${expanded ? "Collapse" : "Expand"} ${toggle.closest("[data-tree-row]")?.dataset.treeId || "item"} descendants`,
    );
  };
  const clearTreeDepthPreset = () => {
    treeDepthControls.forEach((control) => control.setAttribute("aria-pressed", "false"));
  };
  const applyTreeDepth = (requestedDepth) => {
    const maximumRowDepth = requestedDepth === "all" ? Number.POSITIVE_INFINITY : Number(requestedDepth) - 1;
    treeRows.forEach((row) => {
      const rowDepth = Number(row.dataset.treeDepth || 0);
      row.hidden = rowDepth > maximumRowDepth;
      const toggle = row.querySelector("[data-tree-toggle]");
      if (toggle) setTreeToggleExpanded(toggle, rowDepth < maximumRowDepth);
    });
    treeDepthControls.forEach((control) => {
      control.setAttribute("aria-pressed", String(control.dataset.treeDepthControl === requestedDepth));
    });
  };
  treeDepthControls.forEach((control) => {
    control.addEventListener("click", () => applyTreeDepth(control.dataset.treeDepthControl || "all"));
  });
  document.querySelectorAll("[data-tree-toggle]").forEach((toggle) => {
    toggle.addEventListener("click", () => {
      const expanded = toggle.getAttribute("aria-expanded") === "true";
      setTreeToggleExpanded(toggle, !expanded);
      setDescendantsHidden(toggle.closest("[data-tree-row]")?.dataset.treeId || "", expanded);
      clearTreeDepthPreset();
    });
  });

  document.querySelectorAll(".artifact-command-menu").forEach((menu) => {
    menu.addEventListener("toggle", () => {
      if (!menu.open) return;
      document.querySelectorAll(".artifact-command-menu[open]").forEach((other) => {
        if (other !== menu) other.open = false;
      });
    });
  });

  const button = document.querySelector(".dashboard-nav-toggle");
  const navigation = document.querySelector("#fleet-nav");
  if (button && navigation) {
    button.addEventListener("click", () => {
      const expanded = button.getAttribute("aria-expanded") === "true";
      button.setAttribute("aria-expanded", String(!expanded));
      navigation.classList.toggle("is-open", !expanded);
    });
  }

  const recentChanges = document.querySelector("[data-recent-changes]");
  if (recentChanges) {
    const projectKey = recentChanges.dataset.projectKey;
    const viewedAt = recentChanges.dataset.viewedAt;
    const storageKey = `tool-shed:recent-changes:${projectKey}`;
    let previousVisit = 0;
    try {
      previousVisit = Date.parse(window.localStorage.getItem(storageKey) || "") || 0;
    } catch (_error) {
      previousVisit = 0;
    }
    let newCount = 0;
    recentChanges.querySelectorAll("[data-change-at]").forEach((row) => {
      const changedAt = Date.parse(row.dataset.changeAt || "");
      if (!previousVisit || !changedAt || changedAt <= previousVisit) return;
      row.classList.add("is-new-change");
      const badge = row.querySelector(".new-change-badge");
      if (badge) badge.hidden = false;
      newCount += 1;
    });
    const count = recentChanges.querySelector(".new-change-count");
    if (count) count.textContent = previousVisit ? `${newCount} new` : "Visit baseline set";
    try {
      window.localStorage.setItem(storageKey, viewedAt);
    } catch (_error) {
      // Browser-local visit state is optional and never affects active attention.
    }
  }

  const streamUrl = document.body.dataset.dashboardStreamUrl;
  const revision = document.body.dataset.dashboardRevision;
  if (streamUrl && revision && "EventSource" in window) {
    let source = null;

    const closeStream = () => {
      if (!source) return;
      source.close();
      source = null;
    };

    const openStream = () => {
      if (source || document.visibilityState !== "visible") return;
      source = new EventSource(`${streamUrl}?since=${encodeURIComponent(revision)}`);
      source.addEventListener("dashboard-update", () => {
        closeStream();
        window.location.reload();
      });
    };

    window.addEventListener("pagehide", closeStream);
    window.addEventListener("beforeunload", closeStream);
    window.addEventListener("pageshow", openStream);
    document.addEventListener("click", (event) => {
      const targetElement = event.target instanceof Element ? event.target : event.target.parentElement;
      const link = targetElement?.closest("a[href]");
      if (!link) return;
      const target = new URL(link.href, window.location.href);
      if (target.origin === window.location.origin) closeStream();
    }, { capture: true });
    document.addEventListener("submit", closeStream, { capture: true });
    document.addEventListener("visibilitychange", () => {
      if (document.visibilityState === "hidden") {
        closeStream();
      } else {
        openStream();
      }
    });
    openStream();
  }
});
