import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { checkDay, ExportError, mean, pyRound } from "../src/common";
import { parseCsv } from "../src/csv";
import { buildPayload, render } from "../src/payload";
import * as td from "../src/techdisc";
import * as ud from "../src/udisc";

const fixtures = join(dirname(fileURLToPath(import.meta.url)), "..", "..", "tests", "fixtures");
const fixture = (name: string): ud.CsvFile => ({ name, text: readFileSync(join(fixtures, name), "utf-8") });
const sample = fixture("sample.csv");
const throwsCsv = fixture("throws.csv");
const alex = () => ud.loadRounds([sample], "alex");

describe("numbers match Python", () => {
  it("rounds like Python's round()", () => {
    expect(pyRound(0.125, 2)).toBe(0.12); // an exact tie goes to the even neighbour
    expect(pyRound(0.375, 2)).toBe(0.38);
    expect(pyRound(2.5)).toBe(2);
    expect(pyRound(3.5)).toBe(4);
    expect(pyRound(-2.5)).toBe(-2);
    expect(pyRound(1.005, 2)).toBe(1); // 1.005 is really 1.00499999999999989...
    expect(pyRound(2.675, 2)).toBe(2.67);
    expect(pyRound(4.695, 2)).toBe(4.7);
    expect(pyRound(1 / 3, 2)).toBe(0.33);
  });

  it("averages exactly, then rounds once", () => {
    // Cases where a sum divided by n lands on the other side of a tie from statistics.mean.
    expect(pyRound(mean([8.38, 8.14, 2.62, 4.58, 4.33, 4.14]), 2)).toBe(5.37);
    expect(pyRound(mean([1.43, 8.41, 4.1, 8.23, 5.96, 7.6]), 2)).toBe(5.96);
    expect(pyRound(mean([1.64, 6.24, 2.4, 8.97, 3.09, 6.15, 1.99, 8.13, 8.4, 8.54]), 2)).toBe(5.55);
    expect(mean([3, 0, 2])).toBe(5 / 3);
    expect(mean([-1.5, -2.5])).toBe(-2);
    expect(mean([0, 0])).toBe(0);
  });

  it("validates dates", () => {
    expect(checkDay(" 2026-02-28 ", "start")).toBe("2026-02-28");
    expect(checkDay(null, "start")).toBeNull();
    expect(checkDay("", "start")).toBeNull();
    for (const bad of ["2026-3-1", "yesterday", "2026-13-01", "2026-02-30", "20261017"]) {
      expect(() => checkDay(bad, "start")).toThrow(/start must be a date/);
    }
  });
});

describe("csv reader", () => {
  it("handles quotes, embedded commas and newlines, CRLF, a BOM and blank lines", () => {
    const text = '﻿a,b,c\r\n1,"x, y",3\r\n\r\n"line\none","say ""hi""",\r\n4,5\r\n';
    expect(parseCsv(text)).toEqual({
      header: ["a", "b", "c"],
      rows: [
        { a: "1", b: "x, y", c: "3" },
        { a: "line\none", b: 'say "hi"', c: "" },
        { a: "4", b: "5" }, // a short row simply lacks the trailing field
      ],
    });
  });

  it("copes with an empty file", () => {
    expect(parseCsv("")).toEqual({ header: [], rows: [] });
  });
});

describe("dates", () => {
  it("keeps the wall-clock time and offset of a UDisc date", () => {
    const d = ud.parseDate("2026-10-17 1735-0400") as ud.Stamp;
    expect([d.year, d.day, d.month, d.roundId]).toEqual([2026, "2026-10-17", "2026-10", "2026-10-17 1735"]);
    expect(d.offsetMin).toBe(-240);
    expect(d.ms).toBe(Date.UTC(2026, 9, 17, 21, 35));
    expect(d.isoformat()).toBe("2026-10-17T17:35:00-04:00");
    expect((ud.parseDate("2026-01-02 0030+0530") as ud.Stamp).isoformat()).toBe("2026-01-02T00:30:00+05:30");
    expect((ud.parseDate("2026-01-01 2330-0500") as ud.Stamp).day).toBe("2026-01-01"); // wall date, not UTC's
  });

  it("rejects blank and unparseable dates", () => {
    for (const bad of ["", "garbage", "2026-10-17", "2026-13-17 1735-0400", "2026-10-17 2561-0400"]) {
      expect(ud.parseDate(bad)).toBeNull();
    }
    expect(ud.parseDate(null)).toBeNull();
  });

  it("shows throw times in the local zone (tests pin America/New_York)", () => {
    const t = new td.LocalTime(1778166000);
    expect(t.isoformat()).toBe("2026-05-07T11:00:00-04:00");
    expect([t.day, t.month, t.year]).toEqual(["2026-05-07", "2026-05", 2026]);
  });
});

describe("scorecard rules", () => {
  it("filters players case-insensitively and skips Par rows", () => {
    expect(ud.loadRounds([sample], "ALEX")).toHaveLength(5);
    expect(ud.loadRounds([sample], "sam")).toHaveLength(1);
    expect(new Set(ud.loadRounds([sample]).map((r) => r.player))).toEqual(new Set(["Alex", "Sam"]));
    expect(ud.listPlayers([sample])).toEqual([
      { player: "Alex", rounds: 5 },
      { player: "Sam", rounds: 1 },
    ]);
  });

  it("trims trailing blank hole columns and uses the par row", () => {
    const rounds = alex();
    expect(Object.fromEntries(rounds.map((r) => [r.course, r.holes]))).toEqual({ "Pine Hollow": 9, "Oak Ridge": 6 });
    expect(rounds.map((r) => r.toPar)).toEqual([3, 0, 2, 2, 0]);
  });

  it("scores a partial round on its played holes only", () => {
    const partial = alex().at(-1) as ud.Round;
    expect(partial.holes).toBe(9);
    expect(partial.played).toEqual([1, 2, 3, 4]);
    expect([partial.total, partial.par, partial.toPar]).toEqual([13, 13, 0]);
  });

  it("treats 0 as not played, drops all-zero rounds and ignores the Total column", () => {
    const pad = ",".repeat(18);
    const header = sample.text.split("\n")[0];
    const text = [
      header,
      `Par,Test,Main,2026-01-01 1000-0400,2026-01-01 1100-0400,9,,,3,3,3${pad}`,
      `Alex,Test,Main,2026-01-01 1000-0400,2026-01-01 1100-0400,99,0,,3,4,0${pad}`,
      `Par,Test,Main,2026-01-02 1000-0400,2026-01-02 1100-0400,9,,,3,3,3${pad}`,
      `Alex,Test,Main,2026-01-02 1000-0400,2026-01-02 1100-0400,0,0,,0,0,0${pad}`,
    ].join("\n");
    const found = ud.loadRounds([{ name: "x.csv", text }], "Alex");
    expect(found).toHaveLength(1);
    const r = found[0] as ud.Round;
    expect(r.played).toEqual([1, 2]);
    expect([r.total, r.par, r.toPar]).toEqual([7, 6, 1]);
  });

  it("de-duplicates overlapping exports", () => {
    expect(ud.loadRounds([sample, { ...sample, name: "older-export.csv" }], "alex")).toHaveLength(5);
  });

  it("tells the two kinds of file apart by header", () => {
    const files = [sample, throwsCsv];
    expect(ud.scorecardFiles(files).map((f) => f.name)).toEqual(["sample.csv"]);
    expect(td.throwFiles(files).map((f) => f.name)).toEqual(["throws.csv"]);
    expect(ud.loadRounds(files, "alex")).toHaveLength(5);
    expect(td.loadThrows(files)).toHaveLength(7);
  });

  it("explains a missing or wrong file", () => {
    expect(() => ud.loadRounds([throwsCsv])).toThrow(ExportError);
    expect(() => ud.loadRounds([])).toThrow(/No UDisc scorecard/);
    expect(() => td.loadThrows([sample])).toThrow(/No TechDisc throw exports/);
    const noCourse = { name: "bad.csv", text: "PlayerName,StartDate\nAlex,2026-01-01 1000-0400\n" };
    expect(() => ud.loadRounds([noCourse])).toThrow(/missing the CourseName column/);
  });
});

describe("queries", () => {
  it("finds a round by id or by date", () => {
    expect(ud.findRound(alex(), "2026-06-20 1800")[0]?.course).toBe("Oak Ridge");
    expect(ud.findRound(alex(), "2026-06-20")[0]?.course).toBe("Oak Ridge");
    expect(ud.findRound(alex(), "1999-01-01")).toEqual([null, []]);
  });

  it("rejects bad dates and bad groupings", () => {
    expect(() => ud.filterRounds(alex(), { start: "2026-3-1" })).toThrow(RangeError);
    expect(() => td.filterThrows([], { end: "soon" })).toThrow(/end must be a date/);
    expect(() => ud.scoringTrends(alex(), { group_by: "week" as never })).toThrow(/group_by/);
    expect(() => td.throwTrends(td.loadThrows([throwsCsv]), { group_by: "week" as never })).toThrow(/group_by/);
  });

  it("matches the Python tests on the sample data", () => {
    const rounds = alex();
    const stats = ud.courseStats(rounds, "Pine Hollow");
    expect(stats?.rounds).toBe(4);
    expect(stats?.avg_to_par).toBe(pyRound((3 + 0 + 2) / 3, 2));
    expect(stats?.best?.to_par).toBe(0);
    expect(stats?.worst?.to_par).toBe(3);
    expect(stats).not.toHaveProperty("holes");
    expect(ud.courseStats(rounds, "Nowhere")).toBeNull();
    expect(ud.compareSeasons(rounds, 2025, 2026).avg_to_par_change).toBe(0.5);
    expect([-3, -2, -1, 0, 1, 2, 3, 5].map(ud.scoreKind)).toEqual([
      "eagle_or_better", "eagle_or_better", "birdie", "par", "bogey", "double", "triple_or_worse", "triple_or_worse",
    ]);
  });

  it("summarizes throws", () => {
    const stats = td.throwStats(td.loadThrows([throwsCsv]));
    expect(stats.overall.throws).toBe(7);
    expect(stats.overall.max_speed_mph).toBe(49);
    expect(stats.overall.avg_speed_mph).toBe(pyRound((45 + 47 + 40 + 49 + 44 + 42 + 44) / 7, 2));
    expect(stats.by_style[0]?.throws).toBe(3); // most-thrown first
    expect(td.throwStats([], {}).overall.avg_speed_mph).toBeNull();
  });
});

describe("dashboard payload", () => {
  it("embeds only the chosen player and fills the template", () => {
    const rounds = alex();
    const payload = buildPayload(rounds, td.loadThrows([throwsCsv]), "Alex");
    expect(payload.rounds).toHaveLength(5);
    expect(payload.through).toBe("2026-07-01");
    expect(payload.courses.map((c) => [c.key, c.n])).toEqual([["Pine Hollow|Main", 4]]);
    expect(JSON.stringify(payload)).not.toContain("Sam");
  });

  it("escapes anything that could end the script block", () => {
    const payload = { ...buildPayload([], [], "</script><!-- x"), note: "<b>" };
    const html = render(payload, '<script id="data" type="application/json">__DATA__</script>');
    expect(html).not.toContain("__DATA__");
    expect(html.match(/<\/script>/g)).toHaveLength(1);
    expect(html).not.toContain("<!--");
    const embedded = /type="application\/json">(.*)<\/script>/s.exec(html)?.[1] ?? "";
    expect(JSON.parse(embedded).player).toBe("</script><!-- x");
  });
});
