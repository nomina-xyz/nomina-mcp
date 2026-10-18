// Nomina MCP site: install tabs, copy buttons, mobile menu. No dependencies.
(function () {
  "use strict";

  // Install tabs (WAI-ARIA tabs pattern with arrow-key navigation)
  const tablist = document.querySelector('[role="tablist"]');
  if (tablist) {
    const tabs = Array.from(tablist.querySelectorAll('[role="tab"]'));
    const panels = tabs.map((t) => document.getElementById(t.getAttribute("aria-controls")));
    const select = (index, focus) => {
      tabs.forEach((tab, i) => {
        const on = i === index;
        tab.setAttribute("aria-selected", on ? "true" : "false");
        tab.tabIndex = on ? 0 : -1;
        panels[i].hidden = !on;
        panels[i].classList.toggle("active", on);
      });
      if (focus) tabs[index].focus();
    };
    tabs.forEach((tab, i) => {
      tab.addEventListener("click", () => select(i, false));
      tab.addEventListener("keydown", (e) => {
        const n = tabs.length;
        if (e.key === "ArrowRight" || e.key === "ArrowDown") { e.preventDefault(); select((i + 1) % n, true); }
        else if (e.key === "ArrowLeft" || e.key === "ArrowUp") { e.preventDefault(); select((i - 1 + n) % n, true); }
        else if (e.key === "Home") { e.preventDefault(); select(0, true); }
        else if (e.key === "End") { e.preventDefault(); select(n - 1, true); }
      });
    });
  }

  // Copy buttons
  document.querySelectorAll("button.copy[data-copy]").forEach((btn) => {
    const original = btn.textContent;
    btn.addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(btn.dataset.copy);
        btn.textContent = "Copied";
        btn.classList.add("copied");
        setTimeout(() => { btn.textContent = original; btn.classList.remove("copied"); }, 1600);
      } catch (_) {
        btn.textContent = "Select & copy";
        setTimeout(() => { btn.textContent = original; }, 1600);
      }
    });
  });

  // Mobile menu
  const menuButton = document.querySelector(".nav_mob_menu_button");
  const menu = document.getElementById("mobile-menu");
  if (menuButton && menu) {
    const covered = [document.querySelector("main"), document.querySelector("footer")].filter(Boolean);
    const setOpen = (open) => {
      menu.classList.toggle("open", open);
      menuButton.setAttribute("aria-expanded", open ? "true" : "false");
      menuButton.setAttribute("aria-label", open ? "Close menu" : "Open menu");
      document.body.style.overflow = open ? "hidden" : "";
      covered.forEach((el) => { el.inert = open; });
      if (!open && document.activeElement && menu.contains(document.activeElement)) menuButton.focus();
    };
    menuButton.addEventListener("click", () => setOpen(!menu.classList.contains("open")));
    // Any in-page navigation closes the menu, including header buttons that sit above the overlay.
    document.querySelectorAll('a[href^="#"]').forEach((a) => a.addEventListener("click", () => setOpen(false)));
    window.addEventListener("hashchange", () => setOpen(false));
    document.addEventListener("keydown", (e) => { if (e.key === "Escape") setOpen(false); });
  }
})();
