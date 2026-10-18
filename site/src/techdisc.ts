// Parse TechDisc throw exports and compute throw statistics. A port of techdisc_data.py.
//
// Export layout (one row per throw):
// id,time,timeSeconds,speedMph,speedKmh,advanceRatio,spinRpm,launchAngle,noseAngle,hyzerAngle,wobbleAngle,
// distanceFeet,distanceMeters,throwType,primaryThrowType,tags,notes
// The `time` column is display text ("6/6/2026, 11:53:57 AM EDT"); `timeSeconds` (epoch) is used instead and shown in
// the browser's local time zone.
//
// The selected files may also include UDisc scorecard exports. Files are told apart by header.

import { parseCsv } from "./csv";
import { casefold, checkDay, cmp, ExportError, mean, pyRound, toFloat } from "./common";
import type { CsvFile, GroupBy } from "./udisc";

export const MARKER_COLUMN = "speedMph"; // present in throw exports, absent from UDisc scorecards

const pad = (n: number, width = 2) => String(n).padStart(width, "0");

/** A throw time, read in the browser's local zone. */
export class LocalTime {
  readonly date: Date;
  constructor(seconds: number) {
    this.date = new Date(Math.round(seconds * 1000));
  }

  get ms(): number {
    return this.date.getTime();
  }

  get year(): number {
    return this.date.getFullYear();
  }

  /** The local date, YYYY-MM-DD. */
  get day(): string {
    return `${pad(this.year, 4)}-${pad(this.date.getMonth() + 1)}-${pad(this.date.getDate())}`;
  }

  /** YYYY-MM */
  get month(): string {
    return this.day.slice(0, 7);
  }

  /** YYYY-MM-DDTHH:MM:SS+HH:MM, to the second. */
  isoformat(): string {
    const d = this.date;
    const off = -d.getTimezoneOffset();
    const sign = off < 0 ? "-" : "+";
    const time = `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
    return `${this.day}T${time}${sign}${pad(Math.floor(Math.abs(off) / 60))}:${pad(Math.abs(off) % 60)}`;
  }
}

export interface Throw {
  throwId: string;
  when: LocalTime;
  speedMph: number | null;
  spinRpm: number | null;
  advanceRatio: number | null;
  launchAngle: number | null;
  noseAngle: number | null;
  hyzerAngle: number | null;
  wobbleAngle: number | null;
  distanceFt: number | null;
  throwType: string;
  primaryType: string;
  tags: string;
  notes: string;
}

export function isThrowExport(text: string): boolean {
  return parseCsv(text).header.includes(MARKER_COLUMN);
}

export function throwFiles(files: readonly CsvFile[]): CsvFile[] {
  const found = files.filter((f) => isThrowExport(f.text));
  if (!found.length) {
    throw new ExportError(`No TechDisc throw exports (CSV with a ${MARKER_COLUMN} column) among the selected files`);
  }
  return found;
}

/** Load every TechDisc export, oldest first. Throws are de-duplicated on their id. */
export function loadThrows(files: readonly CsvFile[]): Throw[] {
  const found = new Map<string, Throw>();
  for (const file of throwFiles(files)) {
    for (const row of parseCsv(file.text).rows) {
      const seconds = toFloat(row["timeSeconds"]);
      const id = row["id"];
      if (seconds === null || !id) continue;
      found.set(id, {
        throwId: id,
        when: new LocalTime(seconds),
        speedMph: toFloat(row["speedMph"]),
        spinRpm: toFloat(row["spinRpm"]),
        advanceRatio: toFloat(row["advanceRatio"]),
        launchAngle: toFloat(row["launchAngle"]),
        noseAngle: toFloat(row["noseAngle"]),
        hyzerAngle: toFloat(row["hyzerAngle"]),
        wobbleAngle: toFloat(row["wobbleAngle"]),
        distanceFt: toFloat(row["distanceFeet"]),
        throwType: (row["throwType"] ?? "").trim(),
        primaryType: (row["primaryThrowType"] ?? "").trim(),
        tags: (row["tags"] ?? "").trim(),
        notes: (row["notes"] ?? "").trim(),
      });
    }
  }
  return [...found.values()].sort((a, b) => a.when.ms - b.when.ms || cmp(a.throwId, b.throwId));
}

// ---------- queries ----------

const known = (values: Iterable<number | null>): number[] => [...values].filter((v): v is number => v !== null);
const avg = (values: Iterable<number | null>): number | null => {
  const vals = known(values);
  return vals.length ? pyRound(mean(vals), 2) : null;
};
const maxOf = (values: Iterable<number | null>): number | null => {
  const vals = known(values);
  return vals.length ? vals.reduce((a, b) => (b > a ? b : a)) : null;
};

export interface ThrowFilter {
  start?: string | null;
  end?: string | null;
  primary_type?: string | null;
  throw_type?: string | null;
}

/** start/end are ISO dates (YYYY-MM-DD), inclusive. Types match case-insensitively (exact). */
export function filterThrows(throws: readonly Throw[], f: ThrowFilter = {}): Throw[] {
  const start = checkDay(f.start, "start");
  const end = checkDay(f.end, "end");
  return throws.filter((t) => {
    const day = t.when.day;
    if (start && day < start) return false;
    if (end && day > end) return false;
    if (f.primary_type && casefold(t.primaryType) !== casefold(f.primary_type)) return false;
    if (f.throw_type && casefold(t.throwType) !== casefold(f.throw_type)) return false;
    return true;
  });
}

export function summarizeThrow(t: Throw) {
  return {
    throw_id: t.throwId,
    when: t.when.isoformat(),
    primary_type: t.primaryType,
    throw_type: t.throwType,
    speed_mph: t.speedMph,
    distance_ft: t.distanceFt,
    spin_rpm: t.spinRpm,
    launch_angle: t.launchAngle,
    hyzer_angle: t.hyzerAngle,
    nose_angle: t.noseAngle,
    wobble_angle: t.wobbleAngle,
    advance_ratio: t.advanceRatio,
    tags: t.tags,
    notes: t.notes,
  };
}

export function throwGroupStats(ts: readonly Throw[]) {
  return {
    throws: ts.length,
    avg_speed_mph: avg(ts.map((t) => t.speedMph)),
    max_speed_mph: maxOf(ts.map((t) => t.speedMph)),
    avg_distance_ft: avg(ts.map((t) => t.distanceFt)),
    max_distance_ft: maxOf(ts.map((t) => t.distanceFt)),
    avg_spin_rpm: avg(ts.map((t) => t.spinRpm)),
    avg_launch_angle: avg(ts.map((t) => t.launchAngle)),
    avg_hyzer_angle: avg(ts.map((t) => t.hyzerAngle)),
    avg_wobble_angle: avg(ts.map((t) => t.wobbleAngle)),
    avg_advance_ratio: avg(ts.map((t) => t.advanceRatio)),
  };
}

/** Overall stats plus a breakdown by (primary_type, throw_type), most-thrown first. */
export function throwStats(throws: readonly Throw[], range: { start?: string | null; end?: string | null } = {}) {
  const ts = filterThrows(throws, range);
  const groups = new Map<string, { primary: string; kind: string; items: Throw[] }>();
  for (const t of ts) {
    const key = `${t.primaryType}\u0000${t.throwType}`;
    const group = groups.get(key) ?? { primary: t.primaryType, kind: t.throwType, items: [] };
    group.items.push(t);
    groups.set(key, group);
  }
  const byStyle = [...groups.values()]
    .map((g) => ({ primary_type: g.primary, throw_type: g.kind, ...throwGroupStats(g.items) }))
    .sort((a, b) => b.throws - a.throws || cmp(a.primary_type, b.primary_type) || cmp(a.throw_type, b.throw_type));
  return {
    first_throw: ts.length ? (ts[0] as Throw).when.day : null,
    last_throw: ts.length ? (ts[ts.length - 1] as Throw).when.day : null,
    overall: throwGroupStats(ts),
    by_style: byStyle,
  };
}

function bucket(t: Throw, groupBy: GroupBy): string {
  if (groupBy === "season") return String(t.when.year);
  if (groupBy === "month") return t.when.month;
  throw new RangeError("group_by must be 'month' or 'season'");
}

/** Speed, distance and spin per period, oldest first. */
export function throwTrends(
  throws: readonly Throw[],
  opts: { primary_type?: string | null; throw_type?: string | null; group_by?: GroupBy } = {},
) {
  const groupBy = opts.group_by ?? "month";
  const ts = filterThrows(throws, { primary_type: opts.primary_type, throw_type: opts.throw_type });
  const buckets = new Map<string, Throw[]>();
  for (const t of ts) {
    const key = bucket(t, groupBy);
    buckets.set(key, [...(buckets.get(key) ?? []), t]);
  }
  return [...buckets.keys()].sort(cmp).map((period) => ({ period, ...throwGroupStats(buckets.get(period) as Throw[]) }));
}

