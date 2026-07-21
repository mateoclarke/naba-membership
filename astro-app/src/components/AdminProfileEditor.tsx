import { useEffect, useState } from 'react';
import MemberProfileEditor from './MemberProfileEditor';

/**
 * Thin wrapper: reads ?id= from the URL and opens the profile editor in admin mode.
 */
export default function AdminProfileEditor() {
  const [profileId, setProfileId] = useState<number | null>(null);
  const [missing, setMissing] = useState(false);

  useEffect(() => {
    const raw = new URLSearchParams(window.location.search).get('id');
    const n = raw ? Number.parseInt(raw, 10) : NaN;
    if (!Number.isFinite(n) || n <= 0) {
      setMissing(true);
      return;
    }
    setProfileId(n);
  }, []);

  if (missing) {
    return (
      <main style={{ maxWidth: '520px', margin: '0 auto', padding: '2rem 1.5rem' }}>
        <h1 style={{ fontSize: '1.35rem' }}>Missing profile id</h1>
        <p style={{ color: '#555' }}>
          Open this page as <code>/account/admin/profile?id=123</code>, or use Edit from the directory
          while signed in as a WordPress administrator.
        </p>
        <a href="/directory" style={{ color: '#0057b8' }}>
          ← Back to directory
        </a>
      </main>
    );
  }

  if (profileId == null) {
    return (
      <main style={{ maxWidth: '720px', margin: '0 auto', padding: '2rem 1.5rem' }}>
        <p style={{ color: '#555' }}>Loading…</p>
      </main>
    );
  }

  return <MemberProfileEditor adminProfileId={profileId} />;
}
