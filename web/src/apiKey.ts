/**
 * Client-side handling of the optional API key.
 *
 * The key is kept in sessionStorage, not localStorage: a research console is
 * often opened on a shared or lab machine, and a credential that survives until
 * someone explicitly clears site data is a worse default than one that ends
 * with the tab.
 */

const STORAGE_KEY = "aishield.apiKey";

export const API_KEY_HEADER = "X-API-Key";

/** Raised by the API client when the server demands a key we do not have. */
export class UnauthorizedError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "UnauthorizedError";
  }
}

function storage(): Storage | null {
  // Private windows and blocked site data make sessionStorage throw on access.
  try {
    return window.sessionStorage;
  } catch {
    return null;
  }
}

export function readApiKey(): string | null {
  try {
    return storage()?.getItem(STORAGE_KEY) || null;
  } catch {
    return null;
  }
}

export function writeApiKey(key: string): void {
  try {
    storage()?.setItem(STORAGE_KEY, key);
  } catch {
    // A console that cannot persist the key still works for this page load.
  }
}

export function clearApiKey(): void {
  try {
    storage()?.removeItem(STORAGE_KEY);
  } catch {
    // Nothing to clear if storage is unavailable.
  }
}

/** The header to attach, or nothing when the deployment is open. */
export function apiKeyHeaders(): Record<string, string> {
  const key = readApiKey();
  return key ? { [API_KEY_HEADER]: key } : {};
}
