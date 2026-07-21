import { useEffect, useState } from 'react';
import type { CSSProperties } from 'react';
import { canAccessMembershipDirectory } from '../lib/membershipApi';

/**
 * Header Map link — only for active members / WP admins.
 */
export default function MapNavLink({ style }: { style?: CSSProperties } = {}) {
  const [show, setShow] = useState(false);

  useEffect(() => {
    setShow(canAccessMembershipDirectory());
  }, []);

  if (!show) return null;

  return (
    <a href="/map" style={style}>
      Map
    </a>
  );
}
