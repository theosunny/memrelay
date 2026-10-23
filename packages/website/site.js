const toggle = document.querySelector("#nav-toggle");
const panel = document.querySelector("#nav-panel");
const navLinks = [...document.querySelectorAll("#nav-panel a")];
const chapters = ["intro", "ability", "pricing", "contact"]
  .map((id) => document.getElementById(id))
  .filter(Boolean);

toggle?.addEventListener("click", () => {
  const open = !panel.classList.contains("open");
  panel.classList.toggle("open", open);
  toggle.setAttribute("aria-expanded", String(open));
});

panel?.addEventListener("click", (event) => {
  if (event.target.closest("a")) {
    panel.classList.remove("open");
    toggle?.setAttribute("aria-expanded", "false");
  }
});

function setActive(id) {
  for (const link of navLinks) {
    const on = link.getAttribute("href") === `#${id}`;
    link.classList.toggle("is-active", on);
    if (on) link.setAttribute("aria-current", "location");
    else link.removeAttribute("aria-current");
  }
}

function chapterNow() {
  const line = 96;
  let current = chapters[0]?.id || "";
  for (const el of chapters) {
    if (el.getBoundingClientRect().top <= line) current = el.id;
  }
  return current;
}

function jumpTo(id) {
  const target = document.getElementById(id);
  if (!target) return;
  const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  document.documentElement.classList.add("is-jumping");
  target.scrollIntoView({ behavior: reduce ? "auto" : "smooth", block: "start" });
  setActive(id);
  window.setTimeout(() => document.documentElement.classList.remove("is-jumping"), 1000);
}

document.addEventListener("scrollend", () => {
  document.documentElement.classList.remove("is-jumping");
  setActive(chapterNow());
});

document.addEventListener("scroll", () => {
  if (document.documentElement.classList.contains("is-jumping")) return;
  setActive(chapterNow());
}, { passive: true });

for (const link of document.querySelectorAll('a[href^="#"]')) {
  link.addEventListener("click", (event) => {
    const id = (link.getAttribute("href") || "").slice(1);
    if (!id || !document.getElementById(id)) return;
    event.preventDefault();
    history.pushState(null, "", `#${id}`);
    jumpTo(id);
  });
}

window.addEventListener("popstate", () => {
  const id = location.hash.replace("#", "");
  if (id) jumpTo(id);
});

const opened = location.hash.replace("#", "");
if (opened && document.getElementById(opened)) jumpTo(opened);
else setActive("intro");

const downloads = [...document.querySelectorAll("#mac-download, #nav-download")];
const note = document.querySelector("#mac-note");

fetch("https://api.github.com/repos/theosunny/memrelay/releases/latest", {
  headers: { Accept: "application/vnd.github+json" },
})
  .then((res) => (res.ok ? res.json() : Promise.reject(new Error("no release"))))
  .then((rel) => {
    const assets = rel.assets || [];
    const asset =
      assets.find((item) => /\.dmg$/i.test(item.name || "")) ||
      assets.find((item) => /(?:\.app\.zip|-macos\.zip)$/i.test(item.name || ""));
    if (!asset) return;
    for (const button of downloads) {
      button.href = asset.browser_download_url;
      if (button.id === "mac-download") button.textContent = "下载 macOS";
    }
    if (note) note.textContent = rel.tag_name ? `最新版本 ${rel.tag_name}` : "安装包已发布";
  })
  .catch(() => {});
