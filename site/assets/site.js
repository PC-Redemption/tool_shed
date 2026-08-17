(() => {
  "use strict";

  const status = document.querySelector(".copy-status");

  async function copyText(value) {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(value);
      return;
    }
    const field = document.createElement("textarea");
    field.value = value;
    field.setAttribute("readonly", "");
    field.style.position = "fixed";
    field.style.opacity = "0";
    document.body.append(field);
    field.select();
    document.execCommand("copy");
    field.remove();
  }

  document.addEventListener("click", async (event) => {
    const button = event.target.closest(".copy-command");
    if (!button) return;
    const code = button.closest(".copy-block")?.querySelector("code");
    if (!code) return;
    const value = code.textContent.trim();
    try {
      await copyText(value);
      button.textContent = "Copied";
      if (status) status.textContent = `Copied: ${value}`;
      window.setTimeout(() => { button.textContent = button.dataset.label || "Copy"; }, 1600);
    } catch (_error) {
      if (status) status.textContent = "Copy failed. Select the command text and copy it manually.";
    }
  });

  document.querySelectorAll(".copy-command").forEach((button) => {
    button.dataset.label = button.textContent;
  });
})();
