document.addEventListener("DOMContentLoaded", () => {
  const button = document.querySelector(".dashboard-nav-toggle");
  const navigation = document.querySelector("#fleet-nav");
  if (!button || !navigation) return;
  button.addEventListener("click", () => {
    const expanded = button.getAttribute("aria-expanded") === "true";
    button.setAttribute("aria-expanded", String(!expanded));
    navigation.classList.toggle("is-open", !expanded);
  });
});
