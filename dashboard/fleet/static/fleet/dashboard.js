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
