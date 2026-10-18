// What the page does with the files a visitor picks, without any DOM: sort them by header, choose a player and
// build the dashboard payload. Kept separate from main.ts so it can be tested directly.

import { casefold, ExportError } from "./common";
import { buildPayload, type Payload } from "./payload";
import { isThrowExport, loadThrows } from "./techdisc";
import { isScorecardExport, loadRounds, type CsvFile } from "./udisc";

export interface Analysis {
  /** Everyone in the scorecard export, most rounds first. */
  players: { player: string; rounds: number }[];
  /** The player the dashboard is for (null when only a throw export was given). */
  player: string | null;
  payload: Payload;
  /** One line for the status area. */
  summary: string;
  /** Names of files that were neither a scorecard nor a throw export. */
  ignored: string[];
  /** Things worth telling the visitor about their data, e.g. a scratched hole that was left out. */
  notes: string[];
}

const plural = (n: number, word: string) => `${n} ${word}${n === 1 ? "" : "s"}`;

/**
 * Analyze the picked files. `player` chooses whose rounds to show; by default it is the player with the most rounds,
 * who is almost certainly the person who exported. Other players only get the rounds scored together with that
 * person: their TechDisc throws are not in the export.
 */
export function analyze(files: readonly CsvFile[], player: string | null = null): Analysis {
  const cards = files.filter((f) => isScorecardExport(f.text));
  const throwFiles = files.filter((f) => isThrowExport(f.text));
  const ignored = files.filter((f) => !cards.includes(f) && !throwFiles.includes(f)).map((f) => f.name);
  if (!cards.length && !throwFiles.length) {
    throw new ExportError("None of these files look like a UDisc scorecard export or a TechDisc throw export.");
  }

  const everyone = cards.length ? loadRounds(cards) : [];
  const counts = new Map<string, number>();
  for (const r of everyone) counts.set(r.player, (counts.get(r.player) ?? 0) + 1);
  const players = [...counts]
    .map(([name, rounds]) => ({ player: name, rounds }))
    .sort((a, b) => b.rounds - a.rounds || (a.player < b.player ? -1 : 1));

  const main = players[0]?.player ?? null;
  // Use the export's own spelling of the name, whatever case it was asked for in.
  const match = player === null ? undefined : players.find((p) => casefold(p.player) === casefold(player));
  const chosen = match ? match.player : main;
  const rounds = chosen === null ? [] : everyone.filter((r) => casefold(r.player) === casefold(chosen));
  const isMain = chosen === null || (main !== null && casefold(chosen) === casefold(main));
  const throws = throwFiles.length && isMain ? loadThrows(throwFiles) : [];

  const payload = buildPayload(rounds, throws, chosen ?? "TechDisc");
  if (!isMain) payload.note = "only rounds scored together with the main player";

  const parts: string[] = [];
  if (cards.length) parts.push(`${plural(rounds.length, "round")} for ${chosen ?? "nobody"}`);
  if (throwFiles.length) parts.push(`${plural(throws.length, "throw")}${isMain ? "" : " (hidden for other players)"}`);
  if (cards.length && !everyone.length) parts.push("no rounds with scores were found");

  const notes: string[] = [];
  const scratched = rounds.filter((r) => r.scratched.length);
  const gapped = rounds.filter((r) => r.totalGap !== null);
  if (scratched.length) {
    notes.push(
      `${plural(scratched.length, "round")} had a scratched hole left out, because UDisc's own total did not count it ` +
        `(${scratched.map((r) => `${r.start.day}, hole ${r.scratched.join(" and ")}`).join("; ")})`,
    );
  }
  if (gapped.length) {
    notes.push(
      `${plural(gapped.length, "round")} ${gapped.length === 1 ? "has a" : "have a"} UDisc total that does not match the hole scores, ` +
        `so the holes were used as they are (${gapped.map((r) => r.start.day).join(", ")})`,
    );
  }
  return { players, player: chosen, payload, summary: parts.join(", "), ignored, notes };
}
