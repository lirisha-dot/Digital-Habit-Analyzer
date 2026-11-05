document.addEventListener("DOMContentLoaded", () => {
  const burger = document.getElementById("burger"), menu = document.getElementById("menu");
  if (burger) burger.addEventListener("click", () => menu.classList.toggle("open"));
  document.querySelectorAll("form[data-confirm]").forEach(f =>
    f.addEventListener("submit", e => { if (!confirm(f.dataset.confirm)) e.preventDefault(); }));
  setTimeout(() => document.querySelectorAll(".flash").forEach(el => el.style.display = "none"), 5000);
});
const COLORS = ["#4f46e5", "#16a34a", "#f59e0b", "#ef4444", "#06b6d4", "#a855f7", "#64748b"];
