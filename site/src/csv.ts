// A small CSV reader (RFC 4180: quoted fields, doubled quotes, commas and newlines inside quotes, CRLF or LF, a
// leading BOM). Like Python's csv.DictReader it skips blank lines and treats missing trailing fields as absent.

export interface CsvTable {
  header: string[];
  rows: Record<string, string>[];
}

export function parseCsv(text: string): CsvTable {
  const records: string[][] = [];
  let record: string[] = [];
  let field = "";
  let inQuotes = false;
  let sawAny = false; // anything on this line, so a lone "" still counts as a field
  const src = text.charCodeAt(0) === 0xfeff ? text.slice(1) : text;

  const endField = () => {
    record.push(field);
    field = "";
  };
  const endRecord = () => {
    if (sawAny) {
      endField();
      records.push(record);
    }
    record = [];
    field = "";
    sawAny = false;
  };

  for (let i = 0; i < src.length; i++) {
    const c = src[i] as string;
    if (inQuotes) {
      if (c === '"') {
        if (src[i + 1] === '"') {
          field += '"';
          i++;
        } else {
          inQuotes = false;
        }
      } else {
        field += c;
      }
      continue;
    }
    if (c === '"') {
      inQuotes = true;
      sawAny = true;
    } else if (c === ",") {
      sawAny = true;
      endField();
    } else if (c === "\n" || c === "\r") {
      if (c === "\r" && src[i + 1] === "\n") i++;
      endRecord();
    } else {
      sawAny = true;
      field += c;
    }
  }
  endRecord();

  const header = (records.shift() ?? []).map((h) => h.trim());
  const rows = records.map((rec) => {
    const row: Record<string, string> = {};
    header.forEach((name, i) => {
      const value = rec[i];
      if (value !== undefined) row[name] = value;
    });
    return row;
  });
  return { header, rows };
}
