const button = document.querySelector("#mac-download");
const note = document.querySelector("#mac-note");

fetch("https://api.github.com/repos/theosunny/memrelay/releases/latest", {
  headers: { Accept: "application/vnd.github+json" },
})
  .then((res) => (res.ok ? res.json() : Promise.reject(new Error("no release"))))
  .then((rel) => {
    const asset = (rel.assets || []).find((item) => /\.(dmg|app\.zip)$/i.test(item.name || ""));
    if (!asset || !button) return;
    button.href = asset.browser_download_url;
    button.textContent = "下载 macOS";
    if (note) note.textContent = rel.tag_name ? `最新版本 ${rel.tag_name}` : "安装包已发布";
  })
  .catch(() => {});
