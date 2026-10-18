import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { analyze } from "../src/app";
import { ExportError } from "../src/common";
import type { CsvFile } from "../src/udisc";

const fixtures = join(dirname(fileURLToPath(import.meta.url)), "..", "..", "tests", "fixtures");
const fixture = (name: string): CsvFile => ({ name, text: readFileSync(join(fixtures, name), "utf-8") });
const sample = fixture("sample.csv");
const throws = fixture("throws.csv");

describe("analyze", () => {
  it("picks the player with the most rounds and includes their throws", () => {
    const a = analyze([sample, throws]);
    expect(a.player).toBe("Alex");
    expect(a.players).toEqual([
      { player: "Alex", rounds: 5 },
      { player: "Sam", rounds: 1 },
    ]);
    expect(a.payload.player).toBe("Alex");
    expect(a.payload.rounds).toHaveLength(5);
    expect(a.payload.throws).toHaveLength(7);
    expect(a.payload.note).toBeUndefined();
    expect(a.summary).toBe("5 rounds for Alex, 7 throws");
  });

  it("does not depend on the order the files were picked in", () => {
    expect(analyze([throws, sample]).payload).toEqual(analyze([sample, throws]).payload);
  });

  it("shows another player's rounds without the main player's throws or anyone else's rounds", () => {
    const a = analyze([sample, throws], "sam");
    expect(a.player).toBe("Sam");
    expect(a.payload.rounds).toHaveLength(1);
    expect(a.payload.throws).toEqual([]);
    expect(a.payload.note).toMatch(/only rounds scored together/);
    expect(a.summary).toContain("hidden for other players");
    expect(JSON.stringify(a.payload)).not.toContain("Alex");
  });

  it("falls back to the main player when the chosen one is not in the export", () => {
    expect(analyze([sample], "nobody").player).toBe("Alex");
  });

  it("works with scorecards only, or throws only", () => {
    const cards = analyze([sample]);
    expect(cards.payload.throws).toEqual([]);
    expect(cards.summary).toBe("5 rounds for Alex");
    const only = analyze([throws]);
    expect(only.player).toBeNull();
    expect(only.players).toEqual([]);
    expect(only.payload.rounds).toEqual([]);
    expect(only.payload.throws).toHaveLength(7);
    expect(only.summary).toBe("7 throws");
  });

  it("merges overlapping exports", () => {
    expect(analyze([sample, { ...sample, name: "older.csv" }]).payload.rounds).toHaveLength(5);
  });

  it("lists files it could not use, and refuses when none are usable", () => {
    const notes = { name: "notes.csv", text: "a,b\n1,2\n" };
    expect(analyze([sample, notes]).ignored).toEqual(["notes.csv"]);
    expect(() => analyze([notes])).toThrow(ExportError);
    expect(() => analyze([])).toThrow(/None of these files/);
    expect(() => analyze([{ name: "empty.csv", text: "" }])).toThrow(ExportError);
  });

  it("handles a scorecard export with no scored rounds", () => {
    const header = sample.text.split("\n")[0];
    const empty = { name: "x.csv", text: `${header}\nAlex,Test,Main,2026-01-01 1000-0400,2026-01-01 1100-0400,0,0,,0,0,0\n` };
    const a = analyze([empty]);
    expect(a.payload.rounds).toEqual([]);
    expect(a.player).toBeNull();
    expect(a.summary).toContain("no rounds with scores");
  });
});
