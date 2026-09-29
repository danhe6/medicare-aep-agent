export async function newSession() {
  const r = await fetch("/api/session", { method: "POST" });
  return (await r.json()).session_id;
}

export async function getMeta() {
  const r = await fetch("/api/meta");
  return r.ok ? r.json() : null;
}

export async function uploadFile(sessionId, file) {
  const fd = new FormData();
  fd.append("session_id", sessionId);
  fd.append("file", file);
  const r = await fetch("/api/upload", { method: "POST", body: fd });
  if (!r.ok) throw new Error((await r.json()).detail || "Upload failed");
  return (await r.json()).path;
}

/** Streams agent events (server-sent events over a POST). Calls onEvent for each. */
export async function chat(sessionId, message, lang, onEvent, profile = null, mode = null) {
  const r = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId, message, lang, profile, mode }),
  });
  if (!r.ok) {
    const err = new Error(`chat failed: ${r.status}`);
    err.status = r.status;
    throw err;
  }
  const reader = r.body.getReader();
  const dec = new TextDecoder();
  let buf = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    let i;
    while ((i = buf.indexOf("\n\n")) >= 0) {
      const chunk = buf.slice(0, i).trim();
      buf = buf.slice(i + 2);
      if (chunk.startsWith("data:")) onEvent(JSON.parse(chunk.slice(5)));
    }
  }
}
