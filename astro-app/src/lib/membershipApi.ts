/**
 * Browser client for the NaBA membership FastAPI (auth + self-service profile).
 */

export const MEMBER_TOKEN_KEY = 'naba_member_access_token';
export const MEMBER_IS_ADMIN_KEY = 'naba_member_is_admin';
export const MEMBER_STATUS_KEY = 'naba_member_membership_status';
export const ADMIN_SHOW_ALL_KEY = 'naba_admin_show_all';

export function getApiBase(): string {
  const v = import.meta.env.PUBLIC_MEMBERSHIP_API_URL;
  if (typeof v === 'string' && v.trim()) {
    return v.replace(/\/$/, '');
  }
  return '';
}

export function getJoinMembershipUrl(): string {
  const v = import.meta.env.PUBLIC_JOIN_MEMBERSHIP_URL;
  if (typeof v === 'string' && v.trim()) {
    return v.trim();
  }
  return 'https://natural-building-alliance.org/register/';
}

export function getStoredToken(): string | null {
  if (typeof window === 'undefined') return null;
  try {
    return localStorage.getItem(MEMBER_TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setStoredToken(token: string): void {
  localStorage.setItem(MEMBER_TOKEN_KEY, token);
}

export function getStoredIsAdmin(): boolean {
  if (typeof window === 'undefined') return false;
  try {
    return localStorage.getItem(MEMBER_IS_ADMIN_KEY) === '1';
  } catch {
    return false;
  }
}

export function setStoredIsAdmin(isAdmin: boolean): void {
  if (isAdmin) {
    localStorage.setItem(MEMBER_IS_ADMIN_KEY, '1');
  } else {
    localStorage.removeItem(MEMBER_IS_ADMIN_KEY);
    localStorage.removeItem(ADMIN_SHOW_ALL_KEY);
  }
}

export function getStoredMembershipStatus(): string | null {
  if (typeof window === 'undefined') return null;
  try {
    return localStorage.getItem(MEMBER_STATUS_KEY);
  } catch {
    return null;
  }
}

export function setStoredMembershipStatus(status: string | null | undefined): void {
  const v = (status || '').trim().toLowerCase();
  if (v) localStorage.setItem(MEMBER_STATUS_KEY, v);
  else localStorage.removeItem(MEMBER_STATUS_KEY);
}

/** Active NaBA member or WP admin may browse the membership directory. */
export function canAccessMembershipDirectory(): boolean {
  if (!getStoredToken()) return false;
  if (getStoredIsAdmin()) return true;
  return getStoredMembershipStatus() === 'active';
}

export function clearStoredToken(): void {
  localStorage.removeItem(MEMBER_TOKEN_KEY);
  localStorage.removeItem(MEMBER_IS_ADMIN_KEY);
  localStorage.removeItem(MEMBER_STATUS_KEY);
  localStorage.removeItem(ADMIN_SHOW_ALL_KEY);
}

/** Resolve `/uploads/...` to absolute URL for <img src>. */
export function mediaUrl(path: string | null | undefined): string {
  if (!path) return '';
  if (/^https?:\/\//i.test(path)) return path;
  const base = getApiBase();
  if (!base) return path;
  return `${base}${path.startsWith('/') ? '' : '/'}${path}`;
}

export async function apiFetch(
  path: string,
  init: RequestInit & { auth?: boolean } = {}
): Promise<Response> {
  const base = getApiBase();
  if (!base) {
    throw new Error('PUBLIC_MEMBERSHIP_API_URL is not configured.');
  }
  const url = `${base}${path.startsWith('/') ? '' : '/'}${path}`;
  const headers = new Headers(init.headers);
  if (init.body && !(init.body instanceof FormData) && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }
  if (init.auth !== false) {
    const t = getStoredToken();
    if (t) headers.set('Authorization', `Bearer ${t}`);
  }
  return fetch(url, { ...init, headers });
}
