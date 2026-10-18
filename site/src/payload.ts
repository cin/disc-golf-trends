// The JSON the dashboard page renders from. A port of dashboard.build_payload and dashboard.render: the same
// compact keys, so the same dashboard_template.html draws it.

import { cmp } from "./common";
import type { Throw } from "./techdisc";
import type { Round } from "./udisc";

export const MIN_COURSE_ROUNDS = 4; // layouts played at least this often get their own entry in the course filter

export interface Payload {
  player: string;
  through: string | null;
  rounds: ReturnType<typeof roundPayload>[];
  courses: { key: string; course: string; layout: string; n: number }[];
  throws: ReturnType<typeof throwPayload>[];
  note?: string;
}

function roundPayload(r: Round) {
  return {
    i: r.roundId,
    d: r.start.day,
    c: r.course,
    l: r.layout,
    h: r.holes,
    t: r.total,
    p: r.par,
    tp: r.toPar,
    r: r.rating,
    s: r.scores,
    q: r.pars,
    f: r.toPar !== null && r.played.length === r.holes,
  };
}

function throwPayload(t: Throw) {
  return {
    d: t.when.day,
    sp: t.speedMph,
    di: t.distanceFt,
    sr: t.spinRpm,
    la: t.launchAngle,
    hy: t.hyzerAngle,
    pt: t.primaryType,
    tt: t.throwType,
  };
}

/** Rounds are the player's only; courses lists the filterable layouts. */
export function buildPayload(rounds: readonly Round[], throws: readonly Throw[], player: string): Payload {
  const counts = new Map<string, { course: string; layout: string; n: number }>();
  for (const r of rounds) {
    const key = `${r.course}|${r.layout}`;
    const entry = counts.get(key) ?? { course: r.course, layout: r.layout, n: 0 };
    entry.n += 1;
    counts.set(key, entry);
  }
  const courses = [...counts.values()]
    .sort((a, b) => b.n - a.n || cmp(a.course, b.course) || cmp(a.layout, b.layout))
    .filter((c) => c.n >= MIN_COURSE_ROUNDS)
    .map((c) => ({ key: `${c.course}|${c.layout}`, course: c.course, layout: c.layout, n: c.n }));
  const last = rounds[rounds.length - 1];
  return {
    player,
    through: last ? last.start.day : null,
    rounds: rounds.map(roundPayload),
    courses,
    throws: throws.map(throwPayload),
  };
}

/** Fill the template's data slot. "<" is escaped so the data can never end the <script> block (or open "<!--"). */
export function render(payload: Payload, template: string): string {
  const data = JSON.stringify(payload).replace(/</g, "\\u003c");
  return template.split("__DATA__").join(data);
}
