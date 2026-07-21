import { useCallback, useEffect, useState } from 'react';
import type { CSSProperties, FormEvent } from 'react';
import { apiFetch } from '../lib/membershipApi';

type LinkRow = {
  id: number;
  business_profile_id: number;
  member_profile_id: number;
  role_in_business?: string | null;
  can_edit: boolean;
  business_display_name?: string | null;
  member_display_name?: string | null;
  member_email?: string | null;
};

type SearchHit = {
  id: number;
  display_name: string;
  entry_type: string;
  email?: string | null;
  organization?: string | null;
};

const labelStyle: CSSProperties = {
  display: 'block',
  fontWeight: 600,
  marginBottom: '0.35rem',
  fontSize: '0.9rem',
};
const inputStyle: CSSProperties = {
  width: '100%',
  boxSizing: 'border-box',
  padding: '0.55rem 0.65rem',
  fontSize: '0.95rem',
  border: '1px solid #ccc',
  borderRadius: '0.35rem',
};

type Props = {
  profileId: number;
  entryType: string;
};

/**
 * Admin-only UI to link individuals ↔ business/organization profiles.
 */
export default function BusinessTeamAdmin({ profileId, entryType }: Props) {
  const isOrgSide = entryType === 'business' || entryType === 'organization';
  const isIndividual = entryType === 'individual';

  const [links, setLinks] = useState<LinkRow[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const [query, setQuery] = useState('');
  const [hits, setHits] = useState<SearchHit[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [role, setRole] = useState('');
  const [canEdit, setCanEdit] = useState(false);
  const [searching, setSearching] = useState(false);

  const loadLinks = useCallback(async () => {
    setErr(null);
    const param = isOrgSide
      ? `business_id=${profileId}`
      : isIndividual
        ? `member_id=${profileId}`
        : '';
    if (!param) return;
    const r = await apiFetch(`/api/v1/admin/business-members/?${param}`);
    if (!r.ok) {
      setErr(await r.text());
      return;
    }
    const data = (await r.json()) as { items: LinkRow[] };
    setLinks(data.items || []);
  }, [profileId, isOrgSide, isIndividual]);

  useEffect(() => {
    void loadLinks();
  }, [loadLinks]);

  async function runSearch() {
    setErr(null);
    setMessage(null);
    const q = query.trim();
    if (q.length < 2) {
      setErr('Type at least 2 characters to search.');
      return;
    }
    setSearching(true);
    try {
      const entryFilter = isOrgSide ? 'individual' : 'business';
      // Also search organizations when linking from an individual
      const url =
        entryFilter === 'business'
          ? `/api/v1/admin/profiles/?page_size=20&q=${encodeURIComponent(q)}`
          : `/api/v1/admin/profiles/?page_size=20&entry_type=individual&q=${encodeURIComponent(q)}`;
      const r = await apiFetch(url);
      if (!r.ok) {
        setErr(await r.text());
        return;
      }
      const data = (await r.json()) as { items: SearchHit[] };
      let items = data.items || [];
      if (!isOrgSide) {
        items = items.filter(
          (i) => i.entry_type === 'business' || i.entry_type === 'organization'
        );
      }
      // Don't offer profiles already linked
      const linkedIds = new Set(
        links.map((l) => (isOrgSide ? l.member_profile_id : l.business_profile_id))
      );
      items = items.filter((i) => i.id !== profileId && !linkedIds.has(i.id));
      setHits(items);
      setSelectedId(items[0]?.id ?? null);
    } finally {
      setSearching(false);
    }
  }

  async function addLink(evt: FormEvent) {
    evt.preventDefault();
    if (!selectedId) {
      setErr('Select a profile to link.');
      return;
    }
    setBusy(true);
    setErr(null);
    setMessage(null);
    try {
      const body = isOrgSide
        ? {
            business_profile_id: profileId,
            member_profile_id: selectedId,
            role_in_business: role.trim() || null,
            can_edit: canEdit,
          }
        : {
            business_profile_id: selectedId,
            member_profile_id: profileId,
            role_in_business: role.trim() || null,
            can_edit: canEdit,
          };
      const r = await apiFetch('/api/v1/admin/business-members/', {
        method: 'POST',
        body: JSON.stringify(body),
      });
      if (!r.ok) {
        const j = (await r.json().catch(() => ({}))) as { detail?: string };
        setErr(typeof j.detail === 'string' ? j.detail : await r.text());
        return;
      }
      setMessage('Link saved.');
      setQuery('');
      setHits([]);
      setSelectedId(null);
      setRole('');
      setCanEdit(false);
      await loadLinks();
    } finally {
      setBusy(false);
    }
  }

  async function toggleCanEdit(link: LinkRow) {
    setBusy(true);
    setErr(null);
    try {
      const r = await apiFetch(`/api/v1/admin/business-members/${link.id}`, {
        method: 'PATCH',
        body: JSON.stringify({ can_edit: !link.can_edit }),
      });
      if (!r.ok) {
        setErr(await r.text());
        return;
      }
      await loadLinks();
    } finally {
      setBusy(false);
    }
  }

  async function saveRole(link: LinkRow, nextRole: string) {
    setBusy(true);
    setErr(null);
    try {
      const r = await apiFetch(`/api/v1/admin/business-members/${link.id}`, {
        method: 'PATCH',
        body: JSON.stringify({ role_in_business: nextRole.trim() || null }),
      });
      if (!r.ok) {
        setErr(await r.text());
        return;
      }
      await loadLinks();
    } finally {
      setBusy(false);
    }
  }

  async function removeLink(link: LinkRow) {
    if (!window.confirm('Remove this association?')) return;
    setBusy(true);
    setErr(null);
    try {
      const r = await apiFetch(`/api/v1/admin/business-members/${link.id}`, {
        method: 'DELETE',
      });
      if (!r.ok) {
        setErr(await r.text());
        return;
      }
      setMessage('Link removed.');
      await loadLinks();
    } finally {
      setBusy(false);
    }
  }

  if (!isOrgSide && !isIndividual) {
    return null;
  }

  const title = isOrgSide ? 'Team & editors' : 'Business associations';
  const searchLabel = isOrgSide
    ? 'Search individuals to link'
    : 'Search businesses / organizations to link';

  return (
    <section
      style={{
        marginTop: '1.75rem',
        padding: '1.25rem',
        border: '1px solid #e5e5e5',
        borderRadius: '0.75rem',
        background: '#fafafa',
      }}
    >
      <h2 style={{ fontSize: '1.1rem', margin: '0 0 0.35rem 0' }}>{title}</h2>
      <p style={{ margin: '0 0 1rem 0', color: '#666', fontSize: '0.9rem', lineHeight: 1.45 }}>
        Link people to this {isOrgSide ? 'organization' : 'member'}. Only those marked{' '}
        <strong>Can edit</strong> can administer the business profile when signed in.
      </p>

      {links.length === 0 ? (
        <p style={{ color: '#777', fontSize: '0.9rem' }}>No links yet.</p>
      ) : (
        <ul style={{ listStyle: 'none', padding: 0, margin: '0 0 1.25rem 0' }}>
          {links.map((link) => {
            const label = isOrgSide
              ? link.member_display_name || `Member #${link.member_profile_id}`
              : link.business_display_name || `Business #${link.business_profile_id}`;
            const sub = isOrgSide
              ? link.member_email || `id ${link.member_profile_id}`
              : `id ${link.business_profile_id}`;
            const otherId = isOrgSide ? link.member_profile_id : link.business_profile_id;
            return (
              <li
                key={link.id}
                style={{
                  display: 'grid',
                  gap: '0.5rem',
                  padding: '0.75rem 0',
                  borderBottom: '1px solid #e8e8e8',
                }}
              >
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem', alignItems: 'baseline' }}>
                  <strong>{label}</strong>
                  <span style={{ color: '#888', fontSize: '0.85rem' }}>{sub}</span>
                  <a
                    href={`/account/admin/profile?id=${otherId}`}
                    style={{ color: '#0057b8', fontSize: '0.85rem' }}
                  >
                    Open profile
                  </a>
                </div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem', alignItems: 'center' }}>
                  <input
                    style={{ ...inputStyle, maxWidth: '200px' }}
                    defaultValue={link.role_in_business ?? ''}
                    placeholder="Role (Owner, Partner…)"
                    onBlur={(e) => {
                      const next = e.target.value;
                      if ((link.role_in_business ?? '') !== next) {
                        void saveRole(link, next);
                      }
                    }}
                  />
                  <label style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', fontSize: '0.9rem' }}>
                    <input
                      type="checkbox"
                      checked={link.can_edit}
                      disabled={busy}
                      onChange={() => void toggleCanEdit(link)}
                    />
                    Can edit
                  </label>
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => void removeLink(link)}
                    style={{
                      marginLeft: 'auto',
                      border: '1px solid #ccc',
                      background: '#fff',
                      borderRadius: '0.35rem',
                      padding: '0.35rem 0.65rem',
                      cursor: 'pointer',
                      fontSize: '0.85rem',
                    }}
                  >
                    Remove
                  </button>
                </div>
              </li>
            );
          })}
        </ul>
      )}

      <form onSubmit={addLink}>
        <label style={{ display: 'block', marginBottom: '0.75rem' }}>
          <span style={labelStyle}>{searchLabel}</span>
          <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
            <input
              style={{ ...inputStyle, flex: '1 1 200px' }}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Name or email…"
            />
            <button
              type="button"
              onClick={() => void runSearch()}
              disabled={searching}
              style={{
                padding: '0.5rem 1rem',
                borderRadius: '0.35rem',
                border: '1px solid #ccc',
                background: '#fff',
                cursor: 'pointer',
              }}
            >
              {searching ? 'Searching…' : 'Search'}
            </button>
          </div>
        </label>

        {hits.length > 0 ? (
          <label style={{ display: 'block', marginBottom: '0.75rem' }}>
            <span style={labelStyle}>Select result</span>
            <select
              style={inputStyle}
              value={selectedId ?? ''}
              onChange={(e) => setSelectedId(Number(e.target.value) || null)}
            >
              {hits.map((h) => (
                <option key={h.id} value={h.id}>
                  {h.display_name}
                  {h.organization ? ` (${h.organization})` : ''}
                  {h.email ? ` — ${h.email}` : ''} [{h.entry_type}] #{h.id}
                </option>
              ))}
            </select>
          </label>
        ) : null}

        <label style={{ display: 'block', marginBottom: '0.75rem' }}>
          <span style={labelStyle}>Role in business (optional)</span>
          <input
            style={inputStyle}
            value={role}
            onChange={(e) => setRole(e.target.value)}
            placeholder="Owner, Architect, Sales…"
          />
        </label>

        <label style={{ display: 'flex', alignItems: 'center', gap: '0.45rem', marginBottom: '1rem' }}>
          <input type="checkbox" checked={canEdit} onChange={(e) => setCanEdit(e.target.checked)} />
          Can edit this business profile
        </label>

        {err ? (
          <p role="alert" style={{ color: '#b91c1c', fontSize: '0.9rem' }}>
            {err}
          </p>
        ) : null}
        {message ? (
          <p role="status" style={{ color: '#166534', fontSize: '0.9rem' }}>
            {message}
          </p>
        ) : null}

        <button
          type="submit"
          disabled={busy || !selectedId}
          style={{
            padding: '0.55rem 1.25rem',
            borderRadius: '999px',
            border: 'none',
            background: busy || !selectedId ? '#888' : '#333',
            color: '#fff',
            fontWeight: 600,
            cursor: busy || !selectedId ? 'not-allowed' : 'pointer',
          }}
        >
          {busy ? 'Saving…' : 'Add link'}
        </button>
      </form>
    </section>
  );
}
