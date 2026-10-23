const toggle = document.querySelector("#nav-toggle");
const panel = document.querySelector("#nav-panel");

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

const button = document.querySelector("#mac-download");
const note = document.querySelector("#mac-note");

fetch("https://api.github.com/repos/theosunny/memrelay/releases/latest", {
  headers: { Accept: "application/vnd.github+json" },
})
  .then((res) => (res.ok ? res.json() : Promise.reject(new Error("no release"))))
  .then((rel) => {
    const assets = rel.assets || [];
    const asset =
      assets.find((item) => /\.dmg$/i.test(item.name || "")) ||
      assets.find((item) => /\.app\.zip$/i.test(item.name || ""));
    if (!asset || !button) return;
    button.href = asset.browser_download_url;
    button.textContent = "下载 macOS";
    if (note) note.textContent = rel.tag_name ? `最新版本 ${rel.tag_name}` : "安装包已发布";
  })
  .catch(() => {});
