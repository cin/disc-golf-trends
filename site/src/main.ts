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
const pickCard = el<HTMLDetailsElement>("pick-card");
const pickSum = el("pick-sum");
const whoCard = el<HTMLDetailsElement>("who-card");
const whoSum = el("who-sum");
const who = el<HTMLSelectElement>("who");
const result = el("result");
const frame = el<HTMLIFrameElement>("dash");

let files: CsvFile[] = [];

function fail(message: string) {
  error.textContent = message;
  status.textContent = "";
  result.hidden = true;
  whoCard.hidden = true;
  pickCard.open = true; // so the files can be chosen again
}

/** Minimize a setup card to its one-line summary; keyboard focus follows so it is not lost inside the closed card. */
function minimize(card: HTMLDetailsElement, summary: string, into: HTMLElement) {
  const hadFocus = card.contains(document.activeElement);
  into.textContent = `${summary} · click to change`;
  card.open = false;
  if (hadFocus) card.querySelector("summary")?.focus({ preventScroll: true });
}

const fileSummary = (names: string[]) => (names.length > 3 ? `${names.length} files` : names.join(", "));

async function readFiles(picked: File[]): Promise<CsvFile[]> {
  if (picked.length > MAX_FILES) throw new ExportError(`Please pick at most ${MAX_FILES} files at once.`);
  const tooBig = picked.find((f) => f.size > MAX_BYTES);
  if (tooBig) throw new ExportError(`${tooBig.name} is larger than ${MAX_BYTES / 1024 / 1024} MB, which is not a UDisc export.`);
  return Promise.all(picked.map(async (f) => ({ name: f.name, text: await f.text() })));
}

function show(analysis: Analysis, collapsePick: boolean) {
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
  const chosen = analysis.players.find((p) => p.player === analysis.player);
  if (!whoCard.hidden && chosen) minimize(whoCard, `${chosen.player} (${chosen.rounds} ${chosen.rounds === 1 ? "round" : "rounds"})`, whoSum);
  if (collapsePick) minimize(pickCard, fileSummary(files.map((f) => f.name)), pickSum);

  frame.title = `Disc golf dashboard for ${analysis.payload.player}`;
  frame.srcdoc = render(analysis.payload, template);
  result.hidden = false;

  const ignored = analysis.ignored.length ? ` Ignored (not a UDisc or TechDisc export): ${analysis.ignored.join(", ")}.` : "";
  status.textContent = `Showing ${analysis.summary}.${ignored}`;
  error.textContent = "";
}

/** Analyze the current files. New files minimize the picker too; choosing another player only minimizes that card. */
function run(player: string | null = null, collapsePick = true) {
  try {
    show(analyze(files, player), collapsePick);
  } catch (e) {
    fail(e instanceof ExportError || e instanceof RangeError ? e.message : `Could not read those files: ${String(e)}`);
  }
}

async function load(picked: File[]) {
  if (!picked.length) return;
  try {
    files = await readFiles(picked);
  } catch (e) {
    fail(e instanceof Error ? e.message : String(e));
    return;
  }
  run();
}

input.addEventListener("change", () => void load([...(input.files ?? [])]));
who.addEventListener("change", () => run(who.value, false));
el("sample").addEventListener("click", () => {
  files = [
    { name: "sample-scorecards.csv", text: sampleScorecards },
    { name: "sample-throws.csv", text: sampleThrows },
  ];
  run();
});

// Files can be dropped on the whole picker card, so it works while the card is minimized too.
for (const type of ["dragenter", "dragover"]) {
  pickCard.addEventListener(type, (ev) => {
    ev.preventDefault();
    pickCard.classList.add("over");
    drop.classList.add("over");
  });
}
for (const type of ["dragleave", "drop"]) {
  pickCard.addEventListener(type, () => {
    pickCard.classList.remove("over");
    drop.classList.remove("over");
  });
}
pickCard.addEventListener("drop", (ev) => {
  ev.preventDefault();
  void load([...(ev.dataTransfer?.files ?? [])]);
});
// A file dropped outside the zone would make the browser navigate away to it; ignore those.
for (const type of ["dragover", "drop"]) window.addEventListener(type, (ev) => ev.preventDefault());

// Size the frame to fit the dashboard so the page scrolls as one, and follow its tab and window changes. The body is
// measured, not the document: the document is never shorter than the frame, so the frame could only ever grow.
frame.addEventListener("load", () => {
  const doc = frame.contentDocument;
  if (!doc) return;
  const fit = () => {
    frame.style.height = `${Math.ceil(doc.body.getBoundingClientRect().height)}px`;
  };
  fit();
  new ResizeObserver(fit).observe(doc.body);
});

// The dashboard remembers its theme (System, Mocha, ...) in localStorage; follow it here too.
const THEME_KEY = "dgt-theme";
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
