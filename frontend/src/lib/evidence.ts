import type { Tone } from "../components/primitives";
import type { EvidenceRecord, EvidenceStatus, RetrievalMethod, SourceKind } from "./genlayer/charterGate";

/**
 * Presentation rules for the Evidence Vault. Nothing here decides anything: every status, fact, value
 * and hash is read from the contract. This module only chooses words, colours and a pre-flight URL check.
 */

export const SOURCE_KIND_INFO: Record<SourceKind, { label: string; method: RetrievalMethod; help: string }> = {
  STATIC_WEB: {
    label: "Static web page",
    method: "GET",
    help: "Plain HTML or text. Read with an HTTP GET.",
  },
  DYNAMIC_WEB: {
    label: "JavaScript-rendered page",
    method: "RENDER_TEXT",
    help: "A page that needs JavaScript to show its content. Rendered in a browser-like environment and read as text.",
  },
  API: {
    label: "JSON API",
    method: "GET",
    help: "A JSON endpoint. Read with an HTTP GET and canonicalised.",
  },
};

/** How CharterGate actually retrieved the source. Never just "URL checked". */
export function describeRetrieval(r: Pick<EvidenceRecord, "source_kind" | "retrieval_method">): {
  badge: string;
  detail: string;
} {
  if (r.retrieval_method === "RENDER_TEXT") {
    return { badge: "JAVASCRIPT RENDER", detail: "Rendered in a browser-like environment and read as text." };
  }
  return r.source_kind === "API"
    ? { badge: "HTTP GET · JSON API", detail: "A JSON endpoint read with an HTTP GET, then canonicalised." }
    : { badge: "HTTP GET · STATIC PAGE", detail: "A static page read with an HTTP GET." };
}

export const STATUS_INFO: Record<EvidenceStatus, { label: string; tone: Tone; explain: string }> = {
  VERIFIED: {
    label: "VERIFIED",
    tone: "eligible",
    explain: "The source states this, and the validators independently found the same value on their own fetch.",
  },
  UNVERIFIABLE: {
    label: "UNVERIFIABLE",
    tone: "warning",
    explain: "The source was read, but it does not support the claim as stated.",
  },
  SOURCE_UNAVAILABLE: {
    label: "SOURCE UNAVAILABLE",
    tone: "ineligible",
    explain: "The validators could not reach the source.",
  },
  INVALID_SOURCE: {
    label: "INVALID SOURCE",
    tone: "ineligible",
    explain: "The source was reached, but its content could not be used.",
  },
};

const REASONS: Record<string, string> = {
  SUPPORTED: "The source explicitly states the value.",
  NOT_SUPPORTED: "The source does not support the claim.",
  NOT_GROUNDED: "The extracted quote could not be found in the source text, so nothing was recorded.",
  VALUE_NOT_IN_CLAIM: "The source states a different value than the claim.",
  FETCH_FAILED: "The request failed (network error or timeout).",
  TOO_LARGE: "The response was larger than the 2 MB limit.",
  EMPTY_BODY: "The response was empty.",
  NOT_TEXT: "The response was not readable text.",
  INVALID_JSON: "The response was not valid JSON.",
  EMPTY_TEXT: "The page contained no readable text.",
};

export function reasonText(code: string): string {
  const http = /^HTTP_(\d{1,3})$/.exec(code);
  if (http) return http[1] === "0" ? "The server returned an unusable HTTP status." : `The server answered HTTP ${http[1]}.`;
  return REASONS[code] ?? code;
}

export const evidenceLabel = (id: number) => `EVIDENCE #${String(id).padStart(3, "0")}`;

export const shortHash = (hash: string) => (hash.length > 18 ? `${hash.slice(0, 10)}…${hash.slice(-6)}` : hash);

/** "docs.example.org/path" for display; the full URL is always shown as well. */
export function displayHost(url: string): string {
  return url.replace(/^https?:\/\//i, "").replace(/\/$/, "");
}

// ---- fact key ------------------------------------------------------------------------------------

/**
 * The ONE normalisation the contract applies to a fact key: case, whitespace and hyphens. There are no
 * synonym aliases and no fuzzy matching, so `team_allocation` and `team_token_allocation` are different
 * facts. Mirrors the contract's `_canon_fact_key`.
 */
export function canonFactKey(raw: string): string {
  return raw.replace(/\s+/g, " ").trim().toLowerCase().replace(/[ -]/g, "_");
}

/** Mirrors the contract's `_validate_fact_key`. Returns null when the key passes. */
export function checkFactKey(raw: string): UrlProblem | null {
  const key = canonFactKey(raw);
  if (key === "") return { code: "FACT_KEY_EMPTY", message: "Say which fact you are asking about, e.g. team_token_allocation." };
  if (key.length > 64) return { code: "FACT_KEY_TOO_LONG", message: "The fact key is longer than 64 characters." };
  if (!/^[a-z0-9_]{1,64}$/.test(key) || !/[a-z0-9]/.test(key)) {
    return { code: "FACT_KEY_INVALID", message: "Use only letters, digits, spaces, hyphens and underscores." };
  }
  return null;
}

// ---- client-side URL pre-check ------------------------------------------------------------------

export interface UrlProblem {
  /** The contract's stable code (the `EXPECTED:` suffix) that this check mirrors. Also used for fact keys. */
  code: string;
  message: string;
}

const NON_PUBLIC_SUFFIXES = [".localhost", ".local", ".internal", ".lan", ".home", ".corp", ".intranet"];
const problem = (code: string, message: string): UrlProblem => ({ code, message });

/**
 * Mirrors the contract's `_validate_source_url`, step for step, so a bad URL is caught before the user
 * signs anything. The contract remains authoritative: this is a convenience, and it is best-effort
 * syntactic screening, not a network-level safety guarantee (GenVM's web module applies its own checks).
 * Returns null when the URL passes.
 */
export function checkSourceUrl(raw: string): UrlProblem | null {
  const url = raw.trim();
  if (url === "") return problem("SOURCE_URL_EMPTY", "Enter a URL.");
  if (url.length > 500) return problem("SOURCE_URL_TOO_LONG", "The URL is longer than 500 characters.");
  for (const ch of url) {
    const c = ch.codePointAt(0) ?? 0;
    if (c < 0x21 || c > 0x7e || ch === "\\") {
      return problem("SOURCE_URL_INVALID_CHARS", "The URL contains spaces, control characters, a backslash or non-ASCII characters.");
    }
  }
  const lower = url.toLowerCase();
  let rest: string;
  if (lower.startsWith("https://")) rest = url.slice(8);
  else if (lower.startsWith("http://")) rest = url.slice(7);
  else return problem("SOURCE_URL_UNSUPPORTED_SCHEME", "Only http:// and https:// URLs are supported.");

  const authority = rest.split("/")[0].split("?")[0].split("#")[0];
  if (authority === "") return problem("SOURCE_URL_NO_HOST", "The URL has no host.");
  if (authority.includes("@")) return problem("SOURCE_URL_HAS_CREDENTIALS", "URLs with a username or password are not allowed.");
  if (authority.startsWith("[")) return problem("SOURCE_URL_IP_LITERAL", "IP address hosts are not allowed.");

  let host = authority;
  const colon = authority.lastIndexOf(":");
  if (colon >= 0) {
    host = authority.slice(0, colon);
    const port = authority.slice(colon + 1);
    if (!/^\d{1,5}$/.test(port) || Number(port) < 1 || Number(port) > 65535) {
      return problem("SOURCE_URL_BAD_PORT", "The port is not valid.");
    }
  }
  host = host.toLowerCase().replace(/\.+$/, "");
  if (host === "") return problem("SOURCE_URL_NO_HOST", "The URL has no host.");
  if (!/^[a-z0-9.-]+$/.test(host)) return problem("SOURCE_URL_INVALID_HOST", "The host name has invalid characters.");
  const labels = host.split(".");
  if (labels.length < 2) return problem("SOURCE_URL_HOST_NOT_PUBLIC", "Use a public host name such as example.org.");
  if (labels.some((l) => l === "")) return problem("SOURCE_URL_INVALID_HOST", "The host name is malformed.");
  const tld = labels[labels.length - 1];
  if (!(/^[a-z]{2,}$/.test(tld) || tld.startsWith("xn--"))) {
    return problem("SOURCE_URL_HOST_NOT_PUBLIC", "Use a public host name, not an IP address.");
  }
  if (host === "localhost" || NON_PUBLIC_SUFFIXES.some((s) => host.endsWith(s))) {
    return problem("SOURCE_URL_HOST_NOT_PUBLIC", "Local and internal hosts are not allowed.");
  }
  return null;
}
