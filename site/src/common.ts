// Helpers shared by the UDisc and TechDisc modules. Ports of common.py plus the bits of Python's numeric behaviour
// (round, statistics.mean, str.casefold) that the statistics rely on, so both implementations agree to the digit.

export class ExportError extends Error {
  override name = "ExportError";
}

/** Python's str.casefold, close enough for names: "ß" folds to "ss", as upper-then-lower does. */
export const casefold = (s: string): string => s.toUpperCase().toLowerCase();

/** Ordering by UTF-16 code units, for use as a sort comparator. */
export const cmp = (a: string | number, b: string | number): number => (a < b ? -1 : a > b ? 1 : 0);

/**
 * Return value as a normalized YYYY-MM-DD string; null/empty pass through. Throws RangeError otherwise.
 * Mirrors common.check_day (the Python 3.10 behaviour: only the extended ISO form is accepted).
 */
export function checkDay(value: string | null | undefined, name: string): string | null {
  if (!value) return null;
  const trimmed = value.trim();
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(trimmed);
  if (m) {
    const [y, mo, d] = [Number(m[1]), Number(m[2]), Number(m[3])];
    const probe = new Date(Date.UTC(y, mo - 1, d));
    if (y >= 1 && probe.getUTCFullYear() === y && probe.getUTCMonth() === mo - 1 && probe.getUTCDate() === d) {
      return trimmed;
    }
  }
  throw new RangeError(`${name} must be a date like 2026-10-17, got '${value}'`);
}

/** Python's round(x, nd): the nearest value to the exact binary number, ties to even. */
export function pyRound(x: number, nd = 0): number {
  if (!Number.isFinite(x)) return x;
  const sign = x < 0 || Object.is(x, -0) ? -1 : 1;
  const digits = Math.abs(x).toFixed(nd + 25); // exact: toFixed rounds the true binary value
  const cut = digits.length - 25;
  if (digits.slice(cut) === "5" + "0".repeat(24)) {
    // An exact tie (e.g. 0.125 to 2 places): Python rounds to the even neighbour, toFixed rounds up.
    let n = BigInt(digits.slice(0, cut).replace(".", ""));
    if (n % 2n === 1n) n += 1n;
    return (sign * Number(n)) / 10 ** nd;
  }
  return Number(x.toFixed(nd));
}

const bitLength = (n: bigint): number => n.toString(2).length;

/** A finite double as [integer, exponent] with value = integer * 2 ** exponent, exactly. */
function decompose(x: number): [bigint, number] {
  const view = new DataView(new ArrayBuffer(8));
  view.setFloat64(0, x);
  const bits = view.getBigUint64(0);
  const biased = Number((bits >> 52n) & 0x7ffn);
  const fraction = bits & 0xfffffffffffffn;
  const mantissa = biased === 0 ? fraction : fraction | (1n << 52n);
  const value = (bits >> 63n) === 1n ? -mantissa : mantissa;
  return [value, (biased === 0 ? 1 : biased) - 1075];
}

/**
 * statistics.mean for a non-empty list of finite numbers: the exact mean, rounded once to the nearest double
 * (ties to even). A naive or compensated sum divided by n rounds twice and can land on the other side of a
 * rounding tie, which shows up when the result is then rounded to two decimals.
 */
export function mean(values: readonly number[]): number {
  const parts = values.map(decompose);
  const low = parts.reduce((m, [, e]) => Math.min(m, e), Infinity);
  const sum = parts.reduce((acc, [m, e]) => acc + (m << BigInt(e - low)), 0n);
  if (sum === 0n) return 0;
  const negative = sum < 0n;
  const a = negative ? -sum : sum;
  const b = BigInt(values.length);
  // Scale so the integer quotient has 54 or 55 bits, keep the remainder as a sticky bit, then round to 53 bits.
  const k = 54 + bitLength(b) - bitLength(a);
  const numerator = k >= 0 ? a << BigInt(k) : a;
  const denominator = k >= 0 ? b : b << BigInt(-k);
  let q = numerator / denominator;
  const sticky = numerator % denominator !== 0n;
  const drop = bitLength(q) - 53;
  const dropped = q & ((1n << BigInt(drop)) - 1n);
  const half = 1n << BigInt(drop - 1);
  q >>= BigInt(drop);
  if (dropped > half || (dropped === half && (sticky || (q & 1n) === 1n))) q += 1n;
  const result = Number(q) * 2 ** (drop - k + low);
  return negative ? -result : result;
}

/** The first element with the smallest key (Python's min with key=). */
export function minBy<T>(items: readonly T[], key: (item: T) => number): T | undefined {
  let best: T | undefined;
  let bestKey = Infinity;
  for (const item of items) {
    const k = key(item);
    if (best === undefined || k < bestKey) [best, bestKey] = [item, k];
  }
  return best;
}

/** The first element with the largest key (Python's max with key=). */
export function maxBy<T>(items: readonly T[], key: (item: T) => number): T | undefined {
  let best: T | undefined;
  let bestKey = -Infinity;
  for (const item of items) {
    const k = key(item);
    if (best === undefined || k > bestKey) [best, bestKey] = [item, k];
  }
  return best;
}

const INT = /^[+-]?\d+$/;
const FLOAT = /^[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?$/;

export function toInt(raw: unknown): number | null {
  const s = String(raw ?? "").trim();
  return INT.test(s) ? Number(s) : null;
}

export function toFloat(raw: unknown): number | null {
  const s = String(raw ?? "").trim();
  return FLOAT.test(s) ? Number(s) : null;
}
