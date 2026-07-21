import { useEffect, useState } from 'react';
import { canAccessMembershipDirectory } from '../lib/membershipApi';

/**
 * Home-page Member Map card — only for active members / WP admins.
 */
export default function HomeMapCard() {
  const [show, setShow] = useState(false);

  useEffect(() => {
    setShow(canAccessMembershipDirectory());
  }, []);

  if (!show) return null;

  return (
    <a href="/map" style={{ textDecoration: 'none', color: 'inherit' }}>
      <div
        style={{
          borderRadius: '0.75rem',
          padding: '1.5rem',
          border: '1px solid #ddd',
          boxShadow: '0 2px 6px rgba(0,0,0,0.04)',
        }}
      >
        <h2 style={{ marginTop: 0, marginBottom: '0.5rem' }}>Member Map</h2>
        <p style={{ margin: 0, color: '#555' }}>
          View an interactive map of active NaBA members by state.
        </p>
      </div>
    </a>
  );
}
