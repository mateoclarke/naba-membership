import { useState } from 'react';
import type { FormEvent } from 'react';
import { getApiBase, setStoredIsAdmin, setStoredMembershipStatus, setStoredToken } from '../lib/membershipApi';

export default function MemberLoginForm({
  redirectTo,
  compact = false,
}: {
  redirectTo?: string;
  compact?: boolean;
} = {}) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    const base = getApiBase();
    if (!base) {
      setError('Set PUBLIC_MEMBERSHIP_API_URL (e.g. in .env) to your API base URL.');
      return;
    }
    setBusy(true);
    try {
      const r = await fetch(`${base}/api/v1/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
      });
      const data = (await r.json().catch(() => ({}))) as {
        access_token?: string;
        is_admin?: boolean;
        membership_status?: string;
        detail?: string | { msg?: string }[];
      };
      if (!r.ok) {
        const msg =
          typeof data.detail === 'string'
            ? data.detail
            : Array.isArray(data.detail)
              ? data.detail.map((d) => d.msg || '').join(' ')
              : r.statusText;
        setError(msg || 'Login failed');
        return;
      }
      if (!data.access_token) {
        setError('No access token in response');
        return;
      }
      setStoredToken(data.access_token);
      setStoredIsAdmin(Boolean(data.is_admin));
      setStoredMembershipStatus(data.membership_status);
      const params = new URLSearchParams(window.location.search);
      const fallback = '/directory?view=members';
      const next = redirectTo || params.get('redirect') || fallback;
      window.location.href = next.startsWith('/') ? next : fallback;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Network error');
    } finally {
      setBusy(false);
    }
  }

  return (
    <form
      onSubmit={onSubmit}
      style={{
        maxWidth: '420px',
        margin: compact ? '0' : '0 auto',
        padding: compact ? '0' : '2rem 1.5rem',
        border: compact ? 'none' : '1px solid #e0e0e0',
        borderRadius: '0.75rem',
        boxShadow: compact ? 'none' : '0 2px 8px rgba(0,0,0,0.04)',
      }}
    >
      <h1 style={{ marginTop: 0, fontSize: compact ? '1.15rem' : '1.5rem' }}>
        {compact ? 'Sign in' : 'Member sign in'}
      </h1>
      {!compact ? (
        <p style={{ color: '#555', fontSize: '0.95rem', lineHeight: 1.5 }}>
          Use the email and password from your Natural Building Alliance membership account.
        </p>
      ) : null}

      {error ? (
        <p
          role="alert"
          style={{
            color: '#b91c1c',
            background: '#fef2f2',
            padding: '0.75rem 1rem',
            borderRadius: '0.5rem',
            fontSize: '0.9rem',
          }}
        >
          {error}
        </p>
      ) : null}

      <label style={{ display: 'block', marginBottom: '1rem' }}>
        <span style={{ display: 'block', fontWeight: 600, marginBottom: '0.35rem', fontSize: '0.9rem' }}>
          Email or username
        </span>
        <input
          type="text"
          name="username"
          autoComplete="username"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          required
          placeholder="you@example.com"
          style={{
            width: '100%',
            boxSizing: 'border-box',
            padding: '0.6rem 0.75rem',
            fontSize: '1rem',
            border: '1px solid #ccc',
            borderRadius: '0.35rem',
          }}
        />
      </label>

      <label style={{ display: 'block', marginBottom: '1.25rem' }}>
        <span style={{ display: 'block', fontWeight: 600, marginBottom: '0.35rem', fontSize: '0.9rem' }}>
          Password
        </span>
        <input
          type="password"
          name="password"
          autoComplete="current-password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
          style={{
            width: '100%',
            boxSizing: 'border-box',
            padding: '0.6rem 0.75rem',
            fontSize: '1rem',
            border: '1px solid #ccc',
            borderRadius: '0.35rem',
          }}
        />
      </label>

      <button
        type="submit"
        disabled={busy}
        style={{
          width: '100%',
          padding: '0.65rem 1rem',
          fontSize: '1rem',
          fontWeight: 600,
          color: '#fff',
          background: busy ? '#888' : '#333',
          border: 'none',
          borderRadius: '999px',
          cursor: busy ? 'not-allowed' : 'pointer',
        }}
      >
        {busy ? 'Signing in…' : 'Sign in'}
      </button>

      {!compact ? (
        <p style={{ marginTop: '1.25rem', fontSize: '0.85rem', color: '#777' }}>
          <a href="/" style={{ color: '#0057b8' }}>
            ← Back to home
          </a>
        </p>
      ) : null}
    </form>
  );
}
