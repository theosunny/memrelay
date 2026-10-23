import { cpSync, mkdirSync, readFileSync, rmSync } from "node:fs";

const urls = JSON.parse(readFileSync(new URL("./urls.json", import.meta.url), "utf8"));
const html = readFileSync(new URL("./index.html", import.meta.url), "utf8");
for (const key of ["website", "sync", "github", "releases", "spec", "license"]) {
  if (!html.includes(urls[key])) throw new Error(`index.html is missing urls.${key}`);
}
const dist = new URL("./dist/", import.meta.url);
rmSync(dist, { recursive: true, force: true });
mkdirSync(dist, { recursive: true });
for (const name of ["index.html", "styles.css", "site.js", "urls.json"]) {
  cpSync(new URL(`./${name}`, import.meta.url), new URL(name, dist));
}
