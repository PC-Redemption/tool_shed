document.addEventListener("DOMContentLoaded", () => {
  const button = document.querySelector(".dashboard-nav-toggle");
  const navigation = document.querySelector("#fleet-nav");
  if (button && navigation) {
    button.addEventListener("click", () => {
      const expanded = button.getAttribute("aria-expanded") === "true";
      button.setAttribute("aria-expanded", String(!expanded));
      navigation.classList.toggle("is-open", !expanded);
    });
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
