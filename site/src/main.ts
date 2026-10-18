import template from "../../dashboard_template.html?raw";
import sampleScorecards from "../../tests/fixtures/synthetic_scorecards.csv?raw";
import sampleThrows from "../../tests/fixtures/synthetic_throws.csv?raw";
import "./style.css";
import { analyze, type Analysis } from "./app";
import { ExportError } from "./common";
import { render } from "./payload";
import type { CsvFile } from "./udisc";

const MAX_FILES = 12;
const MAX_BYTES = 40 * 1024 * 1024; // per file; a few years of rounds is well under 1 MB

const el = <T extends HTMLElement>(id: string) => document.getElementById(id) as T;
const input = el<HTMLInputElement>("files");
const drop = el("drop");
const status = el("status");
const error = el("error");
const whoCard = el("who-card");
const who = el<HTMLSelectElement>("who");
const result = el("result");
const frame = el<HTMLIFrameElement>("dash");

let files: CsvFile[] = [];

function fail(message: string) {
  error.textContent = message;
  status.textContent = "";
}

async function readFiles(picked: File[]): Promise<CsvFile[]> {
  if (picked.length > MAX_FILES) throw new ExportError(`Please pick at most ${MAX_FILES} files at once.`);
  const tooBig = picked.find((f) => f.size > MAX_BYTES);
  if (tooBig) throw new ExportError(`${tooBig.name} is larger than ${MAX_BYTES / 1024 / 1024} MB, which is not a UDisc export.`);
  return Promise.all(picked.map(async (f) => ({ name: f.name, text: await f.text() })));
}

function show(analysis: Analysis) {
  who.replaceChildren(
    ...analysis.players.map((p) => {
      const option = document.createElement("option");
      option.value = p.player;
      option.textContent = `${p.player} (${p.rounds} ${p.rounds === 1 ? "round" : "rounds"})`;
      return option;
    }),
  );
  if (analysis.player !== null) who.value = analysis.player;
  whoCard.hidden = analysis.players.length < 2;

  frame.title = `Disc golf dashboard for ${analysis.payload.player}`;
  frame.srcdoc = render(analysis.payload, template);
  result.hidden = false;

  const ignored = analysis.ignored.length ? ` Ignored (not a UDisc or TechDisc export): ${analysis.ignored.join(", ")}.` : "";
  status.textContent = `Showing ${analysis.summary}.${ignored}`;
  error.textContent = "";
}

function run(player: string | null = null) {
  try {
    show(analyze(files, player));
  } catch (e) {
    result.hidden = true;
    whoCard.hidden = true;
    fail(e instanceof ExportError || e instanceof RangeError ? e.message : `Could not read those files: ${String(e)}`);
  }
}

async function load(picked: File[]) {
  if (!picked.length) return;
  try {
    files = await readFiles(picked);
  } catch (e) {
    result.hidden = true;
    whoCard.hidden = true;
    fail(e instanceof Error ? e.message : String(e));
    return;
  }
  run();
}

input.addEventListener("change", () => void load([...(input.files ?? [])]));
who.addEventListener("change", () => run(who.value));
el("sample").addEventListener("click", () => {
  files = [
    { name: "sample-scorecards.csv", text: sampleScorecards },
    { name: "sample-throws.csv", text: sampleThrows },
  ];
  run();
});

for (const type of ["dragenter", "dragover"]) {
  drop.addEventListener(type, (ev) => {
    ev.preventDefault();
    drop.classList.add("over");
  });
}
for (const type of ["dragleave", "drop"]) {
  drop.addEventListener(type, () => drop.classList.remove("over"));
}
drop.addEventListener("drop", (ev) => {
  ev.preventDefault();
  void load([...(ev.dataTransfer?.files ?? [])]);
});
// A file dropped outside the zone would make the browser navigate away to it; ignore those.
for (const type of ["dragover", "drop"]) window.addEventListener(type, (ev) => ev.preventDefault());

// Grow the frame to fit the dashboard so the page scrolls as one, and follow its tab and window changes.
frame.addEventListener("load", () => {
  const doc = frame.contentDocument;
  if (!doc) return;
  const fit = () => {
    frame.style.height = `${doc.documentElement.scrollHeight}px`;
  };
  fit();
  new ResizeObserver(fit).observe(doc.body);
});

// The dashboard remembers its theme (System, Mocha, ...) in localStorage; follow it here too.
const THEME_KEY = "dgj-theme";
function applyStoredTheme() {
  try {
    const theme = localStorage.getItem(THEME_KEY);
    if (theme && theme !== "system") document.documentElement.setAttribute("data-theme", theme);
    else document.documentElement.removeAttribute("data-theme");
  } catch {
    /* storage may be blocked */
  }
}
applyStoredTheme();
window.addEventListener("storage", (ev) => {
  if (ev.key === THEME_KEY) applyStoredTheme();
});

if (new URLSearchParams(location.search).has("sample")) el("sample").click();
