// Marks matching words as React nodes. Verse text is never parsed as HTML.
const HL_OPEN = "<hl>";
const HL_CLOSE = "</hl>";

// Dotless dalath-rish → rish (same as backend syriac_norm)
const RISH_MAP = { "\u0716": "\u072A" };

export function consonantal(value) {
  const stripped = String(value ?? "")
    .normalize("NFC")
    .replace(/\p{M}/gu, "");
  let out = "";
  for (const ch of stripped) {
    const mapped = RISH_MAP[ch] || ch;
    if (mapped >= "\u0710" && mapped <= "\u072C") out += mapped;
  }
  return out;
}

export function parseHighlight(marked, plain) {
  const source = marked ?? plain ?? "";
  if (!source.includes(HL_OPEN)) return [{ text: source, hit: false }];
  const out = [];
  let rest = source;
  while (rest.length) {
    const open = rest.indexOf(HL_OPEN);
    if (open === -1) {
      out.push({ text: rest, hit: false });
      break;
    }
    if (open > 0) out.push({ text: rest.slice(0, open), hit: false });
    rest = rest.slice(open + HL_OPEN.length);
    const close = rest.indexOf(HL_CLOSE);
    if (close === -1) {
      out.push({ text: rest, hit: true });
      break;
    }
    out.push({ text: rest.slice(0, close), hit: true });
    rest = rest.slice(close + HL_CLOSE.length);
  }
  return out;
}

export function markTokens(plain, matches) {
  const source = plain ?? "";
  const norms = new Set((matches || []).map(consonantal).filter(Boolean));
  if (!norms.size) return [{ text: source, hit: false }];
  return source.split(/(\s+)/).map((part) => ({
    text: part,
    hit: norms.has(consonantal(part)),
  }));
}

export default function Highlight({ marked, plain, matches, className = "" }) {
  const parts = matches
    ? markTokens(plain ?? "", matches)
    : parseHighlight(marked, plain);
  return (
    <span className={className}>
      {parts.map((part, i) =>
        part.hit ? (
          <strong key={i} className="font-bold">
            {part.text}
          </strong>
        ) : (
          <span key={i}>{part.text}</span>
        ),
      )}
    </span>
  );
}
