export function esc(text: string): string {
  return text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

/** Split "a, b; c\nd" into trimmed, de-duplicated (case-insensitive) items. */
export function parseList(input: string): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const raw of input.split(/[,;\n]+/)) {
    const item = raw.trim().replace(/\s+/g, " ");
    if (!item || item.length > 80) continue;
    const key = item.toLowerCase();
    if (!seen.has(key)) {
      seen.add(key);
      out.push(item);
    }
  }
  return out;
}

export function truncate(text: string, limit: number): string {
  return text.length <= limit ? text : text.slice(0, limit - 1).trimEnd() + "…";
}

const INVITE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789";

export function inviteCode(length = 8): string {
  const bytes = crypto.getRandomValues(new Uint8Array(length));
  return Array.from(bytes, (b) => INVITE_ALPHABET[b % INVITE_ALPHABET.length]).join("");
}
