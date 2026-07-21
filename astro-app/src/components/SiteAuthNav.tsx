import { useEffect, useState } from 'react';
import type { CSSProperties } from 'react';
import { clearStoredToken, getStoredToken } from '../lib/membershipApi';

const linkStyle: CSSProperties = {
  textDecoration: 'none',
  color: '#333',
  background: 'none',
  border: 'none',
  padding: 0,
  font: 'inherit',
  cursor: 'pointer',
};

/**
 * Client-only auth links for the site header (token lives in localStorage).
 */
export default function SiteAuthNav() {
  const [loggedIn, setLoggedIn] = useState(false);

  useEffect(() => {
    setLoggedIn(Boolean(getStoredToken()));
  }, []);

  function signOut() {
    clearStoredToken();
    setLoggedIn(false);
    window.location.href = '/';
  }

  if (!loggedIn) {
    return (
      <a href="/login" style={linkStyle}>
        Sign in
      </a>
    );
  }

  return (
    <>
      <a href="/account/profile" style={linkStyle}>
        Profile
      </a>
      <button type="button" onClick={signOut} style={linkStyle}>
        Sign out
      </button>
    </>
  );
}
