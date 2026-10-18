// The port must give the same answers as the Python implementation. tests/golden.py runs every query over the
// fixtures in tests/fixtures/ and writes golden.json; here the TypeScript runs the same queries over the same CSVs.
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { buildPayload } from "../src/payload";
import * as td from "../src/techdisc";
import * as ud from "../src/udisc";

const here = dirname(fileURLToPath(import.meta.url));
const fixtures = join(here, "..", "..", "tests", "fixtures");
const file = (name: string): ud.CsvFile => ({ name, text: readFileSync(join(fixtures, name), "utf-8") });
const golden = JSON.parse(readFileSync(join(here, "golden.json"), "utf-8")) as Record<string, any>;
for (const k of Object.keys(golden)) golden[k] = JSON.parse(JSON.stringify(golden[k])); // -0 becomes 0, as in norm()

/** JSON round trip: drops undefined and -0, like the Python side's JSON dump did. */
const norm = (x: unknown) => JSON.parse(JSON.stringify(x));

const datasets: Record<string, [string, string]> = {
  sample: ["sample.csv", "throws.csv"],
  synthetic: ["synthetic_scorecards.csv", "synthetic_throws.csv"],
};

const throwSummary = (ts: td.Throw[]) =>
  ts.map((t) => {
    const { when: _when, ...rest } = td.summarizeThrow(t);
    return rest;
  });

for (const [name, [cards, throwFile]] of Object.entries(datasets)) {
  describe(`golden: ${name}`, () => {
    const files = [file(cards), file(throwFile)];
    const want = golden[name];
    const everyone = ud.loadRounds(files);
    const rounds = ud.loadRounds(files, "Alex");
    const throws = td.loadThrows(files);

    it("loads the same rounds", () => {
      expect(norm(rounds.map(ud.roundDetail))).toEqual(want.rounds);
      expect(norm(everyone.map((r) => ({ ...ud.summarizeRound(r), player: r.player })))).toEqual(want.everyone);
      expect([...new Set(rounds.map((r) => r.player))].sort()).toEqual(want.players);
    });

    it("lists courses and hole stats", () => {
      expect(norm(ud.listCourses(rounds))).toEqual(want.list_courses);
      expect(norm(ud.holeStats(rounds))).toEqual(want.hole_stats);
      expect(norm(ud.holeStats(rounds, 3))).toEqual(want.hole_stats_min3);
    });

    it("computes course stats", () => {
      const byCourse = Object.fromEntries(
        ud.listCourses(rounds).map((c) => [c.course, ud.courseStats(rounds, c.course, null, true)]),
      );
      expect(norm(byCourse)).toEqual(want.course_stats);
      expect(norm(ud.courseStats(rounds, "big", "blue"))).toEqual(want.course_stats_layout);
      expect(ud.courseStats(rounds, "Nowhere")).toBeNull();
      expect(want.course_stats_none).toBeNull();
    });

    it("filters rounds", () => {
      const summaries = (rs: ud.Round[]) => norm(rs.map(ud.summarizeRound));
      expect(summaries(ud.filterRounds(rounds, { start: "2025-06-01" }))).toEqual(want.filter.since);
      expect(
        summaries(ud.filterRounds(rounds, { start: "2025-01-01", end: "2025-12-31", course: "oak" })),
      ).toEqual(want.filter.window);
      expect(summaries(ud.filterRounds(rounds, { layout: "main" }))).toEqual(want.filter.layout);
      expect(summaries(ud.filterRounds(rounds, { course: "STRASSE" }))).toEqual(want.filter.casefold);
    });

    it("computes trends and distributions", () => {
      for (const g of ["month", "season"] as const) {
        for (const c of [null, "Pine Hollow"]) {
          expect(norm(ud.scoringTrends(rounds, { course: c, group_by: g }))).toEqual(want.trends[`${g}:${c ?? "None"}`]);
        }
      }
      const d = want.distribution;
      expect(norm(ud.scoringDistribution(rounds))).toEqual(d.all);
      expect(norm(ud.scoringDistribution(rounds, { group_by: "season" }))).toEqual(d.season);
      expect(
        norm(ud.scoringDistribution(rounds, { course: "Pine", group_by: "month", start: "2025-03-01", end: "2026-02-28" })),
      ).toEqual(d.month_course);
      expect(norm(ud.scoringDistribution(rounds, { course: "Nowhere" }))).toEqual(d.none);
    });

    it("reports problem holes and compares seasons", () => {
      const p = want.problems;
      expect(norm(ud.holeProblemReport(rounds))).toEqual(p.default);
      expect(norm(ud.holeProblemReport(rounds, { top_n: 5, min_rounds: 1 }))).toEqual(p.min1_top5);
      expect(norm(ud.holeProblemReport(rounds, { course: "Big Lake", min_rounds: 2 }))).toEqual(p.course);
      const c = want.compare;
      expect(norm(ud.compareSeasons(rounds, 2024, 2025))).toEqual(c.plain);
      expect(norm(ud.compareSeasons(rounds, 2025, 2026, "Pine"))).toEqual(c.course);
      expect(norm(ud.compareSeasons(rounds, 2025, 1999))).toEqual(c.missing);
    });

    it("finds rounds by id and by date", () => {
      const f = want.find_round;
      const middle = rounds[Math.floor(rounds.length / 2)] as ud.Round;
      expect(ud.findRound(rounds, middle.roundId)[0]?.roundId).toBe(f.exact);
      expect(ud.findRound(rounds, middle.start.day)[0]?.roundId).toBe(f.by_day[0]);
      expect(ud.findRound(rounds, "1999-01-01")[1]).toEqual(f.missing);
      if (f.shared_day) {
        const days = rounds.map((r) => r.start.day);
        const shared = days.find((d) => days.filter((x) => x === d).length > 1) as string;
        expect(ud.findRound(rounds, shared)[1]).toEqual(f.shared_day);
      }
    });

    it("loads and queries throws", () => {
      const t = want.throws;
      expect(norm(throwSummary(throws))).toEqual(t.all);
      expect(norm(throwSummary(td.filterThrows(throws, { primary_type: "backhand" })))).toEqual(t.filter.backhand);
      expect(
        norm(throwSummary(td.filterThrows(throws, { throw_type: "FLAT", start: "2026-01-01" }))),
      ).toEqual(t.filter.flat_since);
      expect(
        norm(throwSummary(td.filterThrows(throws, { start: "2025-12-01", end: "2026-02-28" }))),
      ).toEqual(t.filter.window);
      expect(norm(td.throwStats(throws))).toEqual(t.stats);
      expect(norm(td.throwStats(throws, { start: "2026-01-01", end: "2026-03-31" }))).toEqual(t.stats_window);
      expect(norm(td.throwStats(throws, { start: "2099-01-01" }))).toEqual(t.stats_empty);
      expect(norm(td.throwTrends(throws, { group_by: "month" }))).toEqual(t.trends.month);
      expect(norm(td.throwTrends(throws, { group_by: "season" }))).toEqual(t.trends.season);
      expect(norm(td.throwTrends(throws, { primary_type: "Backhand", throw_type: "Hyzer" }))).toEqual(
        t.trends.backhand,
      );
    });

    it("builds the same dashboard payload", () => {
      expect(norm(buildPayload(rounds, throws, rounds[0]?.player ?? ""))).toEqual(want.payload);
    });
  });
}
