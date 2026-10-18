// Parse UDisc scorecard CSV exports and compute scoring statistics. A port of udisc_data.py: same rules, same
// results. The browser has no folder to scan, so the loader takes the text of the files the visitor picked.
//
// Export layout (one row per player per round, preceded by a "Par" pseudo-player row for the same round):
// PlayerName,CourseName,LayoutName,StartDate,EndDate,Total,+/-,RoundRating,Hole1..HoleN
// Dates look like "2026-10-17 1735-0400". Totals are summed from the hole scores; the file's Total column is only
// used to spot a scratched hole (see reconcileTotal).
//
// Result objects keep the Python snake_case keys so the two implementations can be compared field for field.

import { parseCsv } from "./csv";
import { casefold, checkDay, cmp, ExportError, maxBy, mean, minBy, pyRound, toInt } from "./common";

export const PAR_PLAYER = "Par";
export const BLOWUP_OVER_PAR = 2; // a hole this many strokes over par (or worse) counts as a blow-up

export interface CsvFile {
  name: string;
  text: string;
}

/** A moment with the UTC offset it was written in, so the wall-clock date and time survive. */
export class Stamp {
  constructor(
    readonly ms: number,
    readonly offsetMin: number,
  ) {}

  private wall(): Date {
    return new Date(this.ms + this.offsetMin * 60000);
  }

  get year(): number {
    return this.wall().getUTCFullYear();
  }

  /** The wall-clock date, YYYY-MM-DD. */
  get day(): string {
    return this.wall().toISOString().slice(0, 10);
  }

  /** YYYY-MM */
  get month(): string {
    return this.day.slice(0, 7);
  }

  /** YYYY-MM-DD HHMM */
  get roundId(): string {
    const iso = this.wall().toISOString();
    return `${iso.slice(0, 10)} ${iso.slice(11, 13)}${iso.slice(14, 16)}`;
  }

  isoformat(): string {
    const sign = this.offsetMin < 0 ? "-" : "+";
    const abs = Math.abs(this.offsetMin);
    const hh = String(Math.floor(abs / 60)).padStart(2, "0");
    const mm = String(abs % 60).padStart(2, "0");
    return `${this.wall().toISOString().slice(0, 19)}${sign}${hh}:${mm}`;
  }
}

export class Round {
  constructor(
    readonly player: string,
    readonly course: string,
    readonly layout: string,
    readonly start: Stamp,
    readonly end: Stamp | null,
    readonly scores: (number | null)[],
    readonly pars: (number | null)[],
    readonly rating: number | null = null,
    /** Holes (1-based) left out because UDisc's own Total shows they did not count. */
    readonly scratched: number[] = [],
    /** The hole sum minus the file's Total, when that could not be explained. */
    readonly totalGap: number | null = null,
  ) {}

  get roundId(): string {
    return this.start.roundId;
  }

  get holes(): number {
    return this.scores.length;
  }

  /** Hole numbers (1-based) that have a score. */
  get played(): number[] {
    const out: number[] = [];
    this.scores.forEach((s, i) => {
      if (s !== null) out.push(i + 1);
    });
    return out;
  }

  /** Sum of the scored holes (the file's Total is not read here; see reconcileTotal for how it is used). */
  get total(): number | null {
    const done = this.scores.filter((s): s is number => s !== null);
    return done.length ? done.reduce((a, b) => a + b, 0) : null;
  }

  /** Par for the holes that were actually scored; null if par is unknown for any of them. */
  get par(): number | null {
    const pars: (number | null)[] = [];
    const n = Math.min(this.pars.length, this.scores.length);
    for (let i = 0; i < n; i++) if (this.scores[i] !== null) pars.push(this.pars[i] ?? null);
    if (!pars.length || pars.some((p) => p === null)) return null;
    return (pars as number[]).reduce((a, b) => a + b, 0);
  }

  get toPar(): number | null {
    const { par, total } = this;
    return par === null || total === null ? null : total - par;
  }
}

// ---------- parsing ----------

/** Parse "2026-10-17 1735-0400"; returns null for blank or unparseable values. */
export function parseDate(raw: string | null | undefined): Stamp | null {
  const m = /^(\d{4})-(\d{2})-(\d{2}) (\d{2})(\d{2})([+-])(\d{2}):?(\d{2})$/.exec((raw ?? "").trim());
  if (!m) return null;
  const [y, mo, d, h, mi, oh, om] = [m[1], m[2], m[3], m[4], m[5], m[7], m[8]].map(Number) as [
    number, number, number, number, number, number, number,
  ];
  const wall = Date.UTC(y, mo - 1, d, h, mi);
  const probe = new Date(wall);
  if (
    probe.getUTCFullYear() !== y || probe.getUTCMonth() !== mo - 1 || probe.getUTCDate() !== d ||
    h > 23 || mi > 59 || oh > 23 || om > 59
  ) {
    return null;
  }
  const offsetMin = (m[6] === "-" ? -1 : 1) * (oh * 60 + om);
  return new Stamp(wall - offsetMin * 60000, offsetMin);
}

/** A hole score; the export writes 0 for a hole that was not played, which is treated as no score. */
function toScore(raw: unknown): number | null {
  const value = toInt(raw);
  return value ? value : null;
}

function holeColumns(header: readonly string[]): string[] {
  const holes = header.filter((c) => c.startsWith("Hole") && /^\d+$/.test(c.slice(4)));
  return holes.sort((a, b) => Number(a.slice(4)) - Number(b.slice(4)));
}

/**
 * Use the file's Total to spot a scratched hole. Returns [scores, scratched hole numbers, unexplained gap].
 *
 * A hole the player skipped ("-" in the app) still holds a placeholder score in its column, but UDisc leaves it out of
 * its own Total. If the scored holes add up to exactly one hole's score more than Total, that hole did not count, so it
 * is dropped. If no hole or several holes could explain the gap, nothing is dropped and the gap is returned so it can
 * be reported. A missing Total, or one that matches, changes nothing. (Port of udisc_data._reconcile_total.)
 */
export function reconcileTotal(
  values: readonly (number | null)[],
  total: number | null,
): [(number | null)[], number[], number | null] {
  if (total === null) return [[...values], [], null];
  const scored = values.flatMap((v, i) => (v === null ? [] : [[i, v] as const]));
  const gap = scored.reduce((sum, [, v]) => sum + v, 0) - total;
  if (gap === 0) return [[...values], [], null];
  if (gap > 0) {
    const candidates = scored.filter(([, v]) => v === gap).map(([i]) => i);
    if (candidates.length === 1) {
      const fixed = [...values];
      fixed[candidates[0] as number] = null;
      return [fixed, [(candidates[0] as number) + 1], null];
    }
  }
  return [[...values], [], gap];
}

/** Drop trailing blanks: the export always has 21 hole columns, but layouts have fewer holes. */
function trim<T>(values: readonly (T | null)[]): (T | null)[] {
  const out = [...values];
  while (out.length && out[out.length - 1] === null) out.pop();
  return out;
}

export function isScorecardExport(text: string): boolean {
  const { header } = parseCsv(text);
  return header.includes("PlayerName") && header.includes("StartDate");
}

/** The UDisc scorecard exports among the given files. Other CSVs (e.g. a TechDisc throw export) are ignored. */
export function scorecardFiles(files: readonly CsvFile[]): CsvFile[] {
  const found = files.filter((f) => isScorecardExport(f.text));
  if (!found.length) throw new ExportError("No UDisc scorecard CSVs among the selected files");
  return found;
}

const keyOf = (course: string, layout: string, start: Stamp, player?: string): string =>
  [player, course, layout, start.ms].filter((p) => p !== undefined).join("\u0000");

/**
 * Load every scorecard export. Returns rounds sorted by start time (oldest first).
 *
 * Rounds are de-duplicated on (player, course, layout, start), so overlapping exports are harmless.
 * If `player` is given (case-insensitive), only that player's rounds are returned.
 */
export function loadRounds(files: readonly CsvFile[], player: string | null = null): Round[] {
  const parRows = new Map<string, (number | null)[]>();
  const playerRows = new Map<string, { row: Record<string, string>; values: (number | null)[]; start: Stamp }>();
  for (const file of scorecardFiles(files)) {
    const { header, rows } = parseCsv(file.text);
    for (const required of ["CourseName", "LayoutName"]) {
      if (!header.includes(required)) throw new ExportError(`${file.name}: missing the ${required} column`);
    }
    const cols = holeColumns(header);
    for (const row of rows) {
      const start = parseDate(row["StartDate"]);
      if (start === null) continue;
      const values = cols.map((c) => toScore(row[c]));
      const course = row["CourseName"] ?? "";
      const layout = row["LayoutName"] ?? "";
      const name = row["PlayerName"] ?? "";
      if (name === PAR_PLAYER) {
        parRows.set(keyOf(course, layout, start), values);
      } else if (values.some((v) => v !== null)) {
        // skip abandoned rounds with no scores at all
        playerRows.set(keyOf(course, layout, start, name), { row, values, start });
      }
    }
  }
  const rounds: Round[] = [];
  for (const { row, values: rawValues, start } of playerRows.values()) {
    const name = row["PlayerName"] ?? "";
    if (player && casefold(name) !== casefold(player)) continue;
    const [values, scratched, gap] = reconcileTotal(rawValues, toInt(row["Total"]));
    if (values.every((v) => v === null)) continue; // the only scored hole was a scratched one
    const course = row["CourseName"] ?? "";
    const layout = row["LayoutName"] ?? "";
    const pars = parRows.get(keyOf(course, layout, start)) ?? [];
    const holes = Math.max(trim(values).length, trim(pars).length);
    const pad = <T>(xs: (T | null)[]): (T | null)[] => Array.from({ length: holes }, (_, i) => xs[i] ?? null);
    rounds.push(
      new Round(name, course, layout, start, parseDate(row["EndDate"]), pad(values), pad(pars), toInt(row["RoundRating"]), scratched, gap),
    );
  }
  return rounds.sort((a, b) => a.start.ms - b.start.ms || cmp(a.player, b.player));
}

/** The names in the export (not "Par") with how many rounds each has, most rounds first. */
export function listPlayers(files: readonly CsvFile[]): { player: string; rounds: number }[] {
  const counts = new Map<string, number>();
  for (const r of loadRounds(files)) counts.set(r.player, (counts.get(r.player) ?? 0) + 1);
  return [...counts]
    .map(([player, rounds]) => ({ player, rounds }))
    .sort((a, b) => b.rounds - a.rounds || cmp(a.player, b.player));
}

// ---------- queries ----------

export interface RoundFilter {
  start?: string | null;
  end?: string | null;
  course?: string | null;
  layout?: string | null;
}

/** start/end are ISO dates (YYYY-MM-DD), inclusive. course/layout match case-insensitively by substring. */
export function filterRounds(rounds: readonly Round[], f: RoundFilter = {}): Round[] {
  const start = checkDay(f.start, "start");
  const end = checkDay(f.end, "end");
  return rounds.filter((r) => {
    const day = r.start.day;
    if (start && day < start) return false;
    if (end && day > end) return false;
    if (f.course && !casefold(r.course).includes(casefold(f.course))) return false;
    if (f.layout && !casefold(r.layout).includes(casefold(f.layout))) return false;
    return true;
  });
}

export function summarizeRound(r: Round) {
  return {
    round_id: r.roundId,
    date: r.start.day,
    course: r.course,
    layout: r.layout,
    holes: r.holes,
    total: r.total,
    par: r.par,
    to_par: r.toPar,
    rating: r.rating,
    holes_scored: r.played.length,
  };
}

export function roundDetail(r: Round) {
  return {
    ...summarizeRound(r),
    player: r.player,
    scratched_holes: r.scratched,
    total_gap: r.totalGap,
    start: r.start.isoformat(),
    end: r.end ? r.end.isoformat() : null,
    holes_detail: r.pars.map((p, i) => {
      const s = r.scores[i] ?? null;
      return { hole: i + 1, par: p, score: s, to_par: s !== null && p !== null ? s - p : null };
    }),
  };
}

/**
 * Match a round_id ("2026-10-17 1735") or a bare date ("2026-10-17").
 * Returns [round, []] on a match, or [null, candidateIds] when a date matches several rounds.
 */
export function findRound(rounds: readonly Round[], roundId: string): [Round | null, string[]] {
  const exact = rounds.find((r) => r.roundId === roundId);
  if (exact) return [exact, []];
  const byDay = rounds.filter((r) => r.start.day === roundId);
  if (byDay.length === 1) return [byDay[0] as Round, []];
  return [null, byDay.map((r) => r.roundId)];
}

export function listCourses(rounds: readonly Round[]) {
  const groups = new Map<string, Round[]>();
  for (const r of rounds) groups.set(r.course, [...(groups.get(r.course) ?? []), r]);
  const out = [...groups].map(([course, rs]) => ({
    course,
    rounds: rs.length,
    layouts: [...new Set(rs.map((r) => r.layout))].sort(cmp),
    first_played: (rs[0] as Round).start.day,
    last_played: (rs[rs.length - 1] as Round).start.day,
  }));
  return out.sort((a, b) => b.rounds - a.rounds || cmp(a.course, b.course));
}

export function roundStats(rs: readonly Round[]) {
  const scored = rs.filter((r) => r.toPar !== null);
  // best/worst only make sense for complete rounds
  const full = scored.filter((r) => r.played.length === r.holes);
  const best = minBy(full, (r) => r.toPar as number);
  const worst = maxBy(full, (r) => r.toPar as number);
  const ratings = rs.map((r) => r.rating).filter((x): x is number => x !== null);
  return {
    rounds: rs.length,
    avg_total: full.length ? pyRound(mean(full.map((r) => r.total as number)), 2) : null,
    avg_to_par: full.length ? pyRound(mean(full.map((r) => r.toPar as number)), 2) : null,
    best: best ? summarizeRound(best) : null,
    worst: worst ? summarizeRound(worst) : null,
    avg_rating: ratings.length ? pyRound(mean(ratings)) : null,
  };
}

export function holeStats(rounds: readonly Round[], minRounds = 1) {
  const cells = new Map<string, { course: string; layout: string; hole: number; vals: [number, number][] }>();
  for (const r of rounds) {
    r.pars.forEach((p, i) => {
      const s = r.scores[i] ?? null;
      if (s === null || p === null) return;
      const key = [r.course, r.layout, i + 1].join("\u0000");
      const cell = cells.get(key) ?? { course: r.course, layout: r.layout, hole: i + 1, vals: [] };
      cell.vals.push([p, s]);
      cells.set(key, cell);
    });
  }
  const out = [];
  for (const { course, layout, hole, vals } of cells.values()) {
    if (vals.length < minRounds) continue;
    const over = vals.map(([p, s]) => s - p);
    const scores = vals.map(([, s]) => s);
    out.push({
      course,
      layout,
      hole,
      par: (vals[vals.length - 1] as [number, number])[0],
      rounds: vals.length,
      avg_score: pyRound(mean(scores), 2),
      avg_to_par: pyRound(mean(over), 2),
      total_strokes_over_par: over.reduce((a, b) => a + b, 0),
      best: scores.reduce((a, b) => (b < a ? b : a)),
      worst: scores.reduce((a, b) => (b > a ? b : a)),
      blowups: over.filter((o) => o >= BLOWUP_OVER_PAR).length,
    });
  }
  return out;
}

/** Round stats for a course. The full per-hole list is large, so it is only added on request. */
export function courseStats(rounds: readonly Round[], course: string, layout: string | null = null, includeHoles = false) {
  const rs = filterRounds(rounds, { course, layout });
  if (!rs.length) return null;
  const holes = holeStats(rs).sort(
    (a, b) => cmp(a.course, b.course) || cmp(a.layout, b.layout) || a.hole - b.hole,
  );
  const byLayout = new Map<string, { course: string; layout: string; rs: Round[] }>();
  for (const r of rs) {
    const key = `${r.course}\u0000${r.layout}`;
    const group = byLayout.get(key) ?? { course: r.course, layout: r.layout, rs: [] };
    group.rs.push(r);
    byLayout.set(key, group);
  }
  const scored = holes.filter((h) => h.rounds >= 2);
  const out = {
    course,
    ...roundStats(rs),
    layouts: [...byLayout.values()]
      .sort((a, b) => cmp(a.course, b.course) || cmp(a.layout, b.layout))
      .map((g) => ({ course: g.course, layout: g.layout, ...roundStats(g.rs) })),
    best_holes: [...scored].sort((a, b) => a.avg_to_par - b.avg_to_par).slice(0, 3),
    worst_holes: [...scored].sort((a, b) => b.avg_to_par - a.avg_to_par).slice(0, 3),
  };
  return includeHoles ? { ...out, holes } : out;
}

export type GroupBy = "month" | "season";

function bucket(r: Round, groupBy: GroupBy): string {
  if (groupBy === "season") return String(r.start.year);
  if (groupBy === "month") return r.start.month;
  throw new RangeError("group_by must be 'month' or 'season'");
}

/** Average score vs par per period. Only complete rounds with known par are averaged. */
export function scoringTrends(
  rounds: readonly Round[],
  opts: { course?: string | null; layout?: string | null; group_by?: GroupBy } = {},
) {
  const groupBy = opts.group_by ?? "month";
  const rs = filterRounds(rounds, { course: opts.course, layout: opts.layout }).filter(
    (r) => r.toPar !== null && r.played.length === r.holes,
  );
  const buckets = new Map<string, Round[]>();
  for (const r of rs) {
    const key = bucket(r, groupBy);
    buckets.set(key, [...(buckets.get(key) ?? []), r]);
  }
  return [...buckets.keys()].sort(cmp).map((period) => {
    const brs = buckets.get(period) as Round[];
    const ratings = brs.map((r) => r.rating).filter((x): x is number => x !== null);
    const best = minBy(brs, (r) => r.toPar as number) as Round; // earliest round wins a tie
    return {
      period,
      rounds: brs.length,
      avg_to_par: pyRound(mean(brs.map((r) => r.toPar as number)), 2),
      best_to_par: best.toPar,
      best_round: { round_id: best.roundId, date: best.start.day, course: best.course, layout: best.layout },
      avg_rating: ratings.length ? pyRound(mean(ratings)) : null,
    };
  });
}

export const SCORE_KINDS = ["eagle_or_better", "birdie", "par", "bogey", "double", "triple_or_worse"] as const;
export type ScoreKind = (typeof SCORE_KINDS)[number];

export function scoreKind(over: number): ScoreKind {
  if (over <= -2) return "eagle_or_better";
  if (over >= 3) return "triple_or_worse";
  return SCORE_KINDS[over + 2] as ScoreKind;
}

/**
 * How holes were scored relative to par, as counts and percentages of holes played.
 *
 * Counts every scored hole with a known par, including holes from partial rounds. group_by is omitted for one row,
 * or 'month' or 'season'.
 */
export function scoringDistribution(
  rounds: readonly Round[],
  opts: RoundFilter & { group_by?: GroupBy | null } = {},
) {
  const buckets = new Map<string, Record<ScoreKind, number>>();
  for (const r of filterRounds(rounds, opts)) {
    const period = opts.group_by ? bucket(r, opts.group_by) : "all";
    r.pars.forEach((p, i) => {
      const s = r.scores[i] ?? null;
      if (s === null || p === null) return;
      let counts = buckets.get(period);
      if (!counts) {
        counts = Object.fromEntries(SCORE_KINDS.map((k) => [k, 0])) as Record<ScoreKind, number>;
        buckets.set(period, counts);
      }
      counts[scoreKind(s - p)] += 1;
    });
  }
  return [...buckets.keys()].sort(cmp).map((period) => {
    const counts = buckets.get(period) as Record<ScoreKind, number>;
    const holes = Object.values(counts).reduce((a, b) => a + b, 0);
    const percent = Object.fromEntries(SCORE_KINDS.map((k) => [k, pyRound((100 * counts[k]) / holes, 1)]));
    return { period, holes, counts, percent };
  });
}

/** Holes ranked by total strokes lost to par (not per-round average), so frequently played holes count. */
export function holeProblemReport(
  rounds: readonly Round[],
  opts: { course?: string | null; layout?: string | null; top_n?: number; min_rounds?: number } = {},
) {
  const rs = filterRounds(rounds, { course: opts.course, layout: opts.layout });
  const stats = holeStats(rs, opts.min_rounds ?? 3);
  stats.sort((a, b) => b.total_strokes_over_par - a.total_strokes_over_par || b.avg_to_par - a.avg_to_par);
  return stats.slice(0, opts.top_n ?? 10);
}

export function compareSeasons(rounds: readonly Round[], yearA: number, yearB: number, course: string | null = null) {
  const season = (year: number) => ({
    year,
    ...roundStats(filterRounds(rounds, { course }).filter((r) => r.start.year === year)),
  });
  const a = season(yearA);
  const b = season(yearB);
  const delta = a.avg_to_par !== null && b.avg_to_par !== null ? pyRound(b.avg_to_par - a.avg_to_par, 2) : null;
  return { a, b, avg_to_par_change: delta };
}
