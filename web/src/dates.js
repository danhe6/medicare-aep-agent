/** Medicare calendar dates and a small .ics (calendar file) builder. Everything runs in the browser:
 *  nothing about the person is sent anywhere. Dates are the fixed federal enrollment windows. */

const d = (y, m, day) => new Date(y, m - 1, day);
const DAY = 86400000;

/** The fixed windows that matter for the next 12 months, from `now`. */
export function windows(now = new Date()) {
  const y = now.getFullYear();
  const out = [];
  for (const yr of [y - 1, y, y + 1]) {
    out.push({ key: "aep_start", date: d(yr, 10, 15), year: yr + 1 });
    out.push({ key: "aep_end", date: d(yr, 12, 7), year: yr + 1 });
    out.push({ key: "plan_start", date: d(yr + 1, 1, 1), year: yr + 1 });
    out.push({ key: "maoep_end", date: d(yr + 1, 3, 31), year: yr + 1 });
  }
  const today = d(y, now.getMonth() + 1, now.getDate());
  return out.filter((w) => w.date >= today && w.date - today < 366 * DAY).sort((a, b) => a.date - b.date);
}

/** Where we are in the Medicare year: "before" AEP, "aep" (open now), "after" AEP (new plan soon), "maoep". */
export function season(now = new Date()) {
  const y = now.getFullYear(), m = now.getMonth() + 1, day = now.getDate();
  const md = m * 100 + day;
  if (md >= 1015 && md <= 1207) return { key: "aep", end: d(y, 12, 7), year: y + 1 };
  if (md > 1207) return { key: "after", start: d(y + 1, 1, 1), year: y + 1 };
  if (md <= 331) return { key: "maoep", end: d(y, 3, 31), year: y };
  return { key: "before", start: d(y, 10, 15), year: y + 1 };
}

export const daysUntil = (date, now = new Date()) =>
  Math.ceil((d(date.getFullYear(), date.getMonth() + 1, date.getDate()) - d(now.getFullYear(), now.getMonth() + 1, now.getDate())) / DAY);

// ---- .ics ----
const pad = (n) => String(n).padStart(2, "0");
const ymd = (x) => `${x.getFullYear()}${pad(x.getMonth() + 1)}${pad(x.getDate())}`;
const utc = (x) => `${x.getUTCFullYear()}${pad(x.getUTCMonth() + 1)}${pad(x.getUTCDate())}T${pad(x.getUTCHours())}${pad(x.getUTCMinutes())}00Z`;
const esc = (s) => String(s).replace(/\\/g, "\\\\").replace(/;/g, "\\;").replace(/,/g, "\\,").replace(/\n/g, "\\n");

/** events: [{ title, detail, date (all-day) | at (exact time), remindDays }] */
export function buildIcs(events) {
  const stamp = utc(new Date());
  const lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Medicare Helper//EN", "CALSCALE:GREGORIAN", "METHOD:PUBLISH"];
  events.forEach((e, i) => {
    lines.push("BEGIN:VEVENT", `UID:mh-${i}-${e.at ? utc(e.at) : ymd(e.date)}@medicare-helper`, `DTSTAMP:${stamp}`);
    if (e.at) lines.push(`DTSTART:${utc(e.at)}`, `DTEND:${utc(new Date(+e.at + 30 * 60000))}`);
    else lines.push(`DTSTART;VALUE=DATE:${ymd(e.date)}`, `DTEND;VALUE=DATE:${ymd(new Date(+e.date + DAY))}`);
    lines.push(`SUMMARY:${esc(e.title)}`, `DESCRIPTION:${esc(e.detail || "")}`);
    for (const r of e.remind || []) {
      lines.push("BEGIN:VALARM", "ACTION:DISPLAY", `DESCRIPTION:${esc(e.title)}`,
        r.hours ? `TRIGGER:-PT${r.hours}H` : `TRIGGER:-P${r.days}D`, "END:VALARM");
    }
    lines.push("END:VEVENT");
  });
  lines.push("END:VCALENDAR");
  return lines.join("\r\n") + "\r\n";
}

export function downloadIcs(text, filename = "medicare-dates.ics") {
  const url = URL.createObjectURL(new Blob([text], { type: "text/calendar;charset=utf-8" }));
  const a = document.createElement("a");
  a.href = url; a.download = filename; document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
