(() => {
  const root = document.documentElement;
  root.classList.add("js");

  const themeButton = document.querySelector("[data-theme-toggle]");
  const themeLabel = document.querySelector("[data-theme-label]");
  const themes = ["system", "light", "dark"];

  const safeStorage = {
    get(key) {
      try { return window.localStorage.getItem(key); } catch (_) { return null; }
    },
    set(key, value) {
      try { window.localStorage.setItem(key, value); } catch (_) { /* private mode */ }
    }
  };

  const applyTheme = (theme) => {
    const next = themes.includes(theme) ? theme : "system";
    root.dataset.theme = next;
    root.style.colorScheme = next === "system" ? "light dark" : next;
    if (themeLabel) themeLabel.textContent = next[0].toUpperCase() + next.slice(1);
    if (themeButton) themeButton.setAttribute("aria-label", `Color theme: ${next}. Activate to change.`);
  };

  applyTheme(safeStorage.get("goal-ledger-theme") || "system");

  themeButton?.addEventListener("click", () => {
    const current = themes.indexOf(root.dataset.theme || "system");
    const next = themes[(current + 1) % themes.length];
    applyTheme(next);
    safeStorage.set("goal-ledger-theme", next);
  });

  const search = document.querySelector("[data-ledger-search]");
  const state = document.querySelector("[data-ledger-state]");
  const rows = [...document.querySelectorAll("[data-ledger-row]")];
  const count = document.querySelector("[data-result-count]");
  const empty = document.querySelector("[data-empty-filter]");

  const filterRows = () => {
    const query = (search?.value || "").trim().toLocaleLowerCase();
    const selected = state?.value || "all";
    let visible = 0;

    rows.forEach((row) => {
      const haystack = (row.dataset.search || row.textContent || "").toLocaleLowerCase();
      const rowState = row.dataset.state || "unknown";
      const matches = (!query || haystack.includes(query)) && (selected === "all" || selected === rowState);
      row.hidden = !matches;
      if (matches) visible += 1;
    });

    if (count) count.textContent = `${visible} ${visible === 1 ? "entry" : "entries"}`;
    if (empty) empty.hidden = visible !== 0;
  };

  search?.addEventListener("input", filterRows);
  state?.addEventListener("change", filterRows);

  document.addEventListener("keydown", (event) => {
    const target = event.target;
    const typing = target instanceof HTMLInputElement || target instanceof HTMLTextAreaElement || target instanceof HTMLSelectElement;

    if (event.key === "/" && !typing && search) {
      event.preventDefault();
      search.focus();
    }

    if (event.key === "Escape" && search && (search.value || state?.value !== "all")) {
      search.value = "";
      if (state) state.value = "all";
      filterRows();
      search.focus();
    }
  });

  const copyText = async (text) => {
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch (_) {
      const area = document.createElement("textarea");
      area.value = text;
      area.setAttribute("readonly", "");
      area.style.position = "fixed";
      area.style.opacity = "0";
      document.body.appendChild(area);
      let copied = false;
      try {
        area.select();
        copied = document.execCommand("copy");
      } catch (_) {
        copied = false;
      } finally {
        area.remove();
      }
      return copied;
    }
  };

  const setCopyFeedback = (button, copied, fallbackLabel, restoreFocus) => {
    const label = button.querySelector("[data-copy-label]");
    const original = button.dataset.copyDefaultLabel || label?.textContent || fallbackLabel;
    button.dataset.copyDefaultLabel = original;
    if (label && !label.hasAttribute("aria-live")) label.setAttribute("aria-live", "polite");
    if (label) label.textContent = copied ? "Copied" : "Copy failed";
    if (restoreFocus) button.focus({ preventScroll: true });
    window.setTimeout(() => {
      if (label) label.textContent = original;
    }, 1800);
  };

  const copyButton = document.querySelector("[data-copy-recovery]");
  const recovery = document.querySelector("[data-recovery-content]");

  copyButton?.addEventListener("click", async () => {
    if (!recovery) return;
    const restoreFocus = document.activeElement === copyButton;
    const text = recovery.innerText.trim();
    const copied = await copyText(text);
    setCopyFeedback(copyButton, copied, "Copy capsule", restoreFocus);
  });

  document.querySelectorAll("[data-copy-prompt]").forEach((button) => {
    button.addEventListener("click", async () => {
      const reference = button.getAttribute("data-copy-target") || button.getAttribute("data-copy-prompt");
      const targetId = reference?.replace(/^#/, "");
      const prompt = targetId ? document.getElementById(targetId) : null;
      if (!prompt) return;
      const restoreFocus = document.activeElement === button;
      const copied = await copyText(prompt.innerText);
      setCopyFeedback(button, copied, "Copy prompt", restoreFocus);
    });
  });

  if ("IntersectionObserver" in window) {
    const links = [...document.querySelectorAll(".phase-rail a[href^='#']")];
    const sections = links
      .map((link) => document.querySelector(link.getAttribute("href")))
      .filter(Boolean);

    const observer = new IntersectionObserver((entries) => {
      const visible = entries
        .filter((entry) => entry.isIntersecting)
        .sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];
      if (!visible) return;
      links.forEach((link) => link.classList.remove("is-in-view"));
      links
        .filter((link) => link.getAttribute("href") === `#${visible.target.id}`)
        .forEach((link) => link.classList.add("is-in-view"));
    }, { rootMargin: "-20% 0px -65%", threshold: [0.1, 0.5] });

    sections.forEach((section) => observer.observe(section));
  }
})();
