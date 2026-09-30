/** Senior mode shows big Yes / No buttons only when the helper's last question can be answered that way.
 *  "Do you have Medicaid?" -> true.  "What state do you live in?" / "Which one is yours?" -> false. */
// A question word in the first few words means an open answer: "What state…", "Could you tell me which…",
// "¿En qué condado…", "¿Cuántas pastillas…".
const WH = /^(what|which|where|when|how|who|whom|whose|why|qu[eé]|cu[aá]l(es)?|d[oó]nde|cu[aá]ndo|c[oó]mo|cu[aá]nt[oa]s?|qui[eé]n(es)?)$/i;

export function isYesNoQuestion(text) {
  if (!text) return false;
  const t = text.trim();
  if (/\b(yes or no|s[ií] o no)\b/i.test(t)) return true;
  // The last question: text up to the final "?" (allowing a trailing "(Most people take 1.)" hint).
  const m = t.match(/([^.!?\n¿]*)\?\s*(\([^)]*\)\s*)?$/);
  if (!m) return false;
  const q = m[1].replace(/^[\s"“*_-]+/, "").trim();
  if (!q || q.split(/\s+/).slice(0, 5).some((w) => WH.test(w.replace(/[^\p{L}]/gu, "")))) return false;
  if (/\bor\b|\bo\b/i.test(q) && !/\bor not\b|\bo no\b/i.test(q)) return false;  // "A or B?" is a choice, not yes/no
  return true;
}
