import { useCallback, useEffect, useState } from 'react';
import type { CSSProperties } from 'react';
import {
  apiFetch,
  clearStoredToken,
  getApiBase,
  getJoinMembershipUrl,
  getStoredIsAdmin,
  getStoredToken,
  mediaUrl,
} from '../lib/membershipApi';
import BusinessTeamAdmin from './BusinessTeamAdmin';

type MembershipSubscription = {
  membership_id?: number | null;
  subscription_id?: number | null;
  title: string;
  status: string;
  period?: string | null;
  period_type?: string | null;
  created_at?: string | null;
  expires_at?: string | null;
  is_lifetime?: boolean;
};

type ProfileDetail = {
  id: number;
  member_id: number;
  display_name: string;
  email?: string | null;
  entry_type: string;
  bio?: string | null;
  website_url?: string | null;
  phone?: string | null;
  social_json?: string | null;
  social?: Record<string, unknown> | null;
  show_city: boolean;
  show_member_since: boolean;
  allow_connect: boolean;
  services_csv?: string | null;
  regions_csv?: string | null;
  tags_csv?: string | null;
  categories_csv?: string | null;
  materials_csv?: string | null;
  organization?: string | null;
  opted_in: boolean;
  badges_csv?: string | null;
  logo_url?: string | null;
  gallery?: string[];
  membership_status?: string | null;
  subscriptions?: MembershipSubscription[];
};

const CATEGORY_OPTIONS = [
  { value: 'professional', label: 'Professional' },
  { value: 'owner/builder', label: 'Owner/Builder' },
  { value: 'vendor', label: 'Vendor' },
  { value: 'educator', label: 'Educator' },
] as const;

const MATERIAL_OPTIONS = [
  { value: 'adobe', label: 'Adobe' },
  { value: 'compressed earth block (ceb)', label: 'Compressed Earth Block (CEB)' },
  { value: 'rammed earth', label: 'Rammed Earth' },
  { value: 'cob', label: 'Cob' },
  { value: 'light straw clay', label: 'Light Straw Clay' },
  { value: 'hempcrete', label: 'Hempcrete' },
  { value: 'timber framing', label: 'Timber Framing' },
  { value: 'straw bale', label: 'Straw Bale' },
  { value: 'natural plaster', label: 'Natural Plaster' },
] as const;

function parseCsvValues(v?: string | null): string[] {
  if (!v) return [];
  return v
    .split(',')
    .map((s) => s.trim().toLowerCase())
    .filter(Boolean);
}

function toCsv(values: string[]): string | null {
  if (!values.length) return null;
  return values.join(',');
}

function formatMembershipStatus(status?: string | null): string {
  const s = (status || '').trim().toLowerCase();
  if (s === 'active') return 'Active';
  if (s === 'expired') return 'Expired';
  if (s === 'none' || !s) return 'No membership';
  return s.charAt(0).toUpperCase() + s.slice(1);
}

function formatSubscriptionStatus(status: string): string {
  const s = (status || '').trim().toLowerCase();
  if (s === 'active') return 'Active';
  if (s === 'cancelled' || s === 'canceled') return 'Cancelled';
  if (s === 'expired') return 'Expired';
  if (s === 'suspended') return 'Suspended';
  if (s === 'pending') return 'Pending';
  if (!s) return 'Unknown';
  return s.charAt(0).toUpperCase() + s.slice(1);
}

function formatExpiryLabel(sub: MembershipSubscription): string {
  if (sub.is_lifetime) return 'Lifetime membership';
  if (!sub.expires_at) return 'Expiration date unavailable';
  const d = new Date(sub.expires_at.includes('T') ? sub.expires_at : sub.expires_at.replace(' ', 'T'));
  if (Number.isNaN(d.getTime())) return `Expires ${sub.expires_at}`;
  const dateStr = d.toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  });
  const status = (sub.status || '').toLowerCase();
  const now = new Date();
  if (status === 'expired' || d.getTime() < now.getTime()) {
    return `Expired ${dateStr}`;
  }
  return `Expires ${dateStr}`;
}

function subscriptionIsCurrent(sub: MembershipSubscription): boolean {
  const status = (sub.status || '').toLowerCase();
  if (status === 'active') return true;
  if (sub.is_lifetime && status !== 'cancelled' && status !== 'canceled' && status !== 'expired') {
    return true;
  }
  return false;
}

type MyBusiness = {
  business_id: number;
  display_name: string;
  role_in_business?: string | null;
  can_edit: boolean;
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

export default function MemberProfileEditor({
  adminProfileId,
}: {
  adminProfileId?: number;
} = {}) {
  const isAdminMode = typeof adminProfileId === 'number' && adminProfileId > 0;
  const [phase, setPhase] = useState<'loading' | 'unauthenticated' | 'forbidden' | 'ready' | 'error'>('loading');
  const [message, setMessage] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [profile, setProfile] = useState<ProfileDetail | null>(null);

  const [bio, setBio] = useState('');
  const [websiteUrl, setWebsiteUrl] = useState('');
  const [phone, setPhone] = useState('');
  const [socialJson, setSocialJson] = useState('');
  const [organization, setOrganization] = useState('');
  const [servicesCsv, setServicesCsv] = useState('');
  const [regionsCsv, setRegionsCsv] = useState('');
  const [tagsCsv, setTagsCsv] = useState('');
  const [categories, setCategories] = useState<string[]>([]);
  const [materials, setMaterials] = useState<string[]>([]);
  const [showCity, setShowCity] = useState(true);
  const [showMemberSince, setShowMemberSince] = useState(true);
  const [allowConnect, setAllowConnect] = useState(false);
  const [optedIn, setOptedIn] = useState(false);
  const [badgesCsv, setBadgesCsv] = useState('');
  const [entryType, setEntryType] = useState('individual');

  const [saving, setSaving] = useState(false);
  const [savingBusiness, setSavingBusiness] = useState(false);
  const [uploadingLogo, setUploadingLogo] = useState(false);
  const [uploadingGallery, setUploadingGallery] = useState(false);
  const [logoUrlInput, setLogoUrlInput] = useState('');
  const [savingLogoUrl, setSavingLogoUrl] = useState(false);
  const [businesses, setBusinesses] = useState<MyBusiness[]>([]);
  const [selectedBusinessId, setSelectedBusinessId] = useState<number | null>(null);
  const [businessProfile, setBusinessProfile] = useState<ProfileDetail | null>(null);

  function profileBasePath(): string {
    if (isAdminMode) return `/api/v1/admin/profiles/${adminProfileId}`;
    return '/api/v1/me/profile';
  }

  function syncFormFromProfile(p: ProfileDetail) {
    setBio(p.bio ?? '');
    setWebsiteUrl(
      typeof p.website_url === 'string' ? p.website_url : p.website_url != null ? String(p.website_url) : ''
    );
    setPhone(p.phone ?? '');
    if (p.social_json && p.social_json.trim()) {
      setSocialJson(p.social_json);
    } else if (p.social && typeof p.social === 'object') {
      setSocialJson(JSON.stringify(p.social, null, 2));
    } else {
      setSocialJson('');
    }
    setOrganization(p.organization ?? '');
    setServicesCsv(p.services_csv ?? '');
    setRegionsCsv(p.regions_csv ?? '');
    setTagsCsv(p.tags_csv ?? '');
    setCategories(parseCsvValues(p.categories_csv));
    setMaterials(parseCsvValues(p.materials_csv));
    setShowCity(p.show_city);
    setShowMemberSince(p.show_member_since);
    setAllowConnect(p.allow_connect);
    setOptedIn(Boolean(p.opted_in));
    setBadgesCsv(p.badges_csv ?? '');
    setEntryType(p.entry_type || 'individual');
    setLogoUrlInput(
      typeof p.logo_url === 'string' && /^https?:\/\//i.test(p.logo_url) ? p.logo_url : ''
    );
  }

  const loadProfile = useCallback(async () => {
    setErr(null);
    setMessage(null);
    const base = getApiBase();
    if (!base) {
      setPhase('error');
      setErr('Configure PUBLIC_MEMBERSHIP_API_URL (e.g. copy astro-app/.env.example to .env).');
      return;
    }
    if (!getStoredToken()) {
      setPhase('unauthenticated');
      return;
    }
    if (isAdminMode && !getStoredIsAdmin()) {
      setPhase('forbidden');
      return;
    }
    const r = await apiFetch(profileBasePath());
    if (r.status === 401) {
      clearStoredToken();
      setPhase('unauthenticated');
      return;
    }
    if (r.status === 403) {
      setPhase('forbidden');
      return;
    }
    if (!r.ok) {
      const t = await r.text();
      setPhase('error');
      setErr(t || r.statusText);
      return;
    }
    const p = (await r.json()) as ProfileDetail;
    setProfile(p);
    syncFormFromProfile(p);
    if (!isAdminMode) {
      const rb = await apiFetch('/api/v1/me/businesses');
      if (rb.ok) {
        setBusinesses((await rb.json()) as MyBusiness[]);
      } else {
        setBusinesses([]);
      }
    } else {
      setBusinesses([]);
    }
    setPhase('ready');
  }, [adminProfileId, isAdminMode]);

  async function loadBusinessProfile(businessId: number) {
    setErr(null);
    setMessage(null);
    const r = await apiFetch(`/api/v1/me/businesses/${businessId}/profile`);
    if (!r.ok) {
      const t = await r.text();
      setErr(t || 'Could not load business profile');
      return;
    }
    setSelectedBusinessId(businessId);
    setBusinessProfile((await r.json()) as ProfileDetail);
  }

  useEffect(() => {
    void loadProfile();
  }, [loadProfile]);

  async function saveProfile(evt: React.FormEvent) {
    evt.preventDefault();
    setErr(null);
    setMessage(null);
    let body: Record<string, unknown> = {
      bio: bio || null,
      website_url: websiteUrl.trim() || null,
      phone: phone.trim() || null,
      organization: organization.trim() || null,
      services_csv: servicesCsv.trim() || null,
      regions_csv: regionsCsv.trim() || null,
      tags_csv: tagsCsv.trim() || null,
      categories_csv: toCsv(categories),
      materials_csv: toCsv(materials),
      show_city: showCity,
      show_member_since: showMemberSince,
      allow_connect: allowConnect,
    };
    if (isAdminMode) {
      body.opted_in = optedIn;
      body.badges_csv = badgesCsv.trim() || null;
      body.entry_type = entryType;
    }
    const sj = socialJson.trim();
    if (sj) {
      try {
        JSON.parse(sj);
      } catch {
        setErr('Social links must be valid JSON (e.g. {"instagram": "https://…"}).');
        return;
      }
      body.social_json = sj;
    } else {
      body.social_json = null;
    }

    setSaving(true);
    try {
      const r = await apiFetch(profileBasePath(), {
        method: 'PUT',
        body: JSON.stringify(body),
      });
      if (r.status === 401) {
        clearStoredToken();
        setPhase('unauthenticated');
        return;
      }
      if (!r.ok) {
        const j = (await r.json().catch(() => ({}))) as { detail?: string };
        setErr(typeof j.detail === 'string' ? j.detail : 'Save failed');
        return;
      }
      const p = (await r.json()) as ProfileDetail;
      setProfile(p);
      syncFormFromProfile(p);
      setMessage('Profile saved.');
    } catch (saveErr) {
      setErr(saveErr instanceof Error ? saveErr.message : 'Save failed');
    } finally {
      setSaving(false);
    }
  }

  async function saveLogoFromUrl(evt: React.FormEvent) {
    evt.preventDefault();
    setErr(null);
    setMessage(null);
    const url = logoUrlInput.trim();
    if (!url) {
      setErr('Enter an image URL (https://…).');
      return;
    }
    if (!/^https?:\/\//i.test(url)) {
      setErr('Logo URL must start with http:// or https://');
      return;
    }
    setSavingLogoUrl(true);
    try {
      const r = await apiFetch(profileBasePath(), {
        method: 'PUT',
        body: JSON.stringify({ logo_url: url }),
      });
      if (r.status === 401) {
        clearStoredToken();
        setPhase('unauthenticated');
        return;
      }
      if (!r.ok) {
        const j = (await r.json().catch(() => ({}))) as { detail?: string | { msg?: string }[] };
        const detail = j.detail;
        const msg =
          typeof detail === 'string'
            ? detail
            : Array.isArray(detail)
              ? detail.map((d) => (typeof d === 'object' && d && 'msg' in d ? String(d.msg) : '')).join(' ')
              : 'Could not save logo URL';
        setErr(msg || 'Could not save logo URL');
        return;
      }
      const p = (await r.json()) as ProfileDetail;
      setProfile(p);
      syncFormFromProfile(p);
      setMessage('Logo updated from URL.');
    } catch (e) {
      setErr(e instanceof Error ? e.message : 'Could not save logo URL');
    } finally {
      setSavingLogoUrl(false);
    }
  }

  async function clearLogoUrl() {
    setErr(null);
    setMessage(null);
    setSavingLogoUrl(true);
    try {
      const r = await apiFetch(profileBasePath(), {
        method: 'PUT',
        body: JSON.stringify({ logo_url: null }),
      });
      if (!r.ok) {
        setErr(await r.text());
        return;
      }
      const p = (await r.json()) as ProfileDetail;
      setProfile(p);
      syncFormFromProfile(p);
      setLogoUrlInput('');
      setMessage('Logo cleared.');
    } catch (e) {
      setErr(e instanceof Error ? e.message : 'Could not clear logo');
    } finally {
      setSavingLogoUrl(false);
    }
  }

  async function onLogoChange(files: FileList | null) {
    const f = files?.[0];
    if (!f) return;
    setUploadingLogo(true);
    setErr(null);
    setMessage(null);
    try {
      const fd = new FormData();
      fd.append('file', f);
      const r = await apiFetch(`${profileBasePath()}/logo`, {
        method: 'POST',
        body: fd,
        headers: {},
      });
      if (r.status === 401) {
        clearStoredToken();
        setPhase('unauthenticated');
        return;
      }
      if (!r.ok) {
        setErr(await r.text());
        return;
      }
      if (isAdminMode) {
        await loadProfile();
        setMessage('Logo updated.');
      } else {
        const p = (await r.json()) as ProfileDetail;
        setProfile(p);
        syncFormFromProfile(p);
        setMessage('Logo updated.');
      }
    } catch (e) {
      setErr(e instanceof Error ? e.message : 'Upload failed');
    } finally {
      setUploadingLogo(false);
    }
  }

  async function onGalleryChange(files: FileList | null) {
    if (!files?.length) return;
    setUploadingGallery(true);
    setErr(null);
    setMessage(null);
    try {
      const fd = new FormData();
      for (let i = 0; i < files.length; i++) {
        fd.append('files', files[i]);
      }
      const r = await apiFetch(`${profileBasePath()}/gallery`, {
        method: 'POST',
        body: fd,
        headers: {},
      });
      if (r.status === 401) {
        clearStoredToken();
        setPhase('unauthenticated');
        return;
      }
      if (!r.ok) {
        setErr(await r.text());
        return;
      }
      if (isAdminMode) {
        await loadProfile();
        setMessage('Gallery updated.');
      } else {
        const j = (await r.json()) as { profile: ProfileDetail };
        setProfile(j.profile);
        setMessage('Gallery updated.');
      }
    } catch (e) {
      setErr(e instanceof Error ? e.message : 'Upload failed');
    } finally {
      setUploadingGallery(false);
    }
  }

  function logout() {
    clearStoredToken();
    window.location.href = '/login';
  }

  function toggleSelected(value: string, current: string[], setter: (next: string[]) => void) {
    const has = current.includes(value);
    if (has) {
      setter(current.filter((v) => v !== value));
      return;
    }
    setter([...current, value]);
  }

  async function saveBusinessProfile(evt: React.FormEvent) {
    evt.preventDefault();
    if (!selectedBusinessId || !businessProfile) return;
    setSavingBusiness(true);
    setErr(null);
    setMessage(null);
    try {
      const r = await apiFetch(`/api/v1/me/businesses/${selectedBusinessId}/profile`, {
        method: 'PUT',
        body: JSON.stringify({
          bio: businessProfile.bio ?? null,
          website_url: businessProfile.website_url ?? null,
          phone: businessProfile.phone ?? null,
          organization: businessProfile.organization ?? null,
          services_csv: businessProfile.services_csv ?? null,
          regions_csv: businessProfile.regions_csv ?? null,
          tags_csv: businessProfile.tags_csv ?? null,
          show_city: businessProfile.show_city,
          show_member_since: businessProfile.show_member_since,
          allow_connect: businessProfile.allow_connect,
        }),
      });
      if (!r.ok) {
        setErr(await r.text());
        return;
      }
      setBusinessProfile((await r.json()) as ProfileDetail);
      setMessage('Business profile saved.');
    } finally {
      setSavingBusiness(false);
    }
  }

  if (phase === 'loading') {
    return (
      <main style={{ maxWidth: '720px', margin: '0 auto', padding: '2rem 1.5rem' }}>
        <p style={{ color: '#555' }}>Loading your profile…</p>
      </main>
    );
  }

  if (phase === 'unauthenticated') {
    const redirect = isAdminMode
      ? `/account/admin/profile?id=${adminProfileId}`
      : '/account/profile';
    return (
      <main style={{ maxWidth: '520px', margin: '0 auto', padding: '2rem 1.5rem' }}>
        <h1 style={{ fontSize: '1.35rem' }}>{isAdminMode ? 'Admin' : 'Account'}</h1>
        <p style={{ color: '#555', lineHeight: 1.5 }}>
          {isAdminMode
            ? 'Sign in with a WordPress administrator account to edit directory profiles.'
            : 'Sign in with your NaBA website credentials to edit your directory profile.'}
        </p>
        <a
          href={`/login?redirect=${encodeURIComponent(redirect)}`}
          style={{
            display: 'inline-block',
            marginTop: '0.5rem',
            padding: '0.55rem 1.25rem',
            background: '#333',
            color: '#fff',
            textDecoration: 'none',
            borderRadius: '999px',
            fontWeight: 600,
          }}
        >
          Sign in
        </a>
      </main>
    );
  }

  if (phase === 'forbidden') {
    return (
      <main style={{ maxWidth: '520px', margin: '0 auto', padding: '2rem 1.5rem' }}>
        <h1 style={{ fontSize: '1.35rem' }}>Admin access required</h1>
        <p style={{ color: '#555', lineHeight: 1.5 }}>
          Your account is signed in but does not have the WordPress administrator role.
        </p>
        <a href="/account/profile" style={{ color: '#0057b8' }}>
          Back to your profile
        </a>
      </main>
    );
  }

  if (phase === 'error') {
    return (
      <main style={{ maxWidth: '720px', margin: '0 auto', padding: '2rem 1.5rem' }}>
        <p style={{ color: '#b91c1c' }}>{err}</p>
        <button type="button" onClick={() => void loadProfile()} style={{ marginTop: '1rem' }}>
          Retry
        </button>
      </main>
    );
  }

  return (
    <main style={{ maxWidth: '720px', margin: '0 auto', padding: '2rem 1.5rem' }}>
      <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: '1rem', flexWrap: 'wrap' }}>
        <h1 style={{ margin: 0, fontSize: '1.5rem' }}>
          {isAdminMode ? 'Edit directory profile (admin)' : 'Your directory profile'}
        </h1>
        <button
          type="button"
          onClick={logout}
          style={{
            padding: '0.4rem 0.9rem',
            fontSize: '0.9rem',
            border: '1px solid #ccc',
            background: '#fff',
            borderRadius: '0.35rem',
            cursor: 'pointer',
          }}
        >
          Sign out
        </button>
      </div>

      {profile ? (
        <section
          style={{
            marginTop: '1.25rem',
            padding: '1rem 1.25rem',
            background: '#f9f9f9',
            borderRadius: '0.5rem',
            fontSize: '0.9rem',
            color: '#444',
          }}
        >
          <p style={{ margin: '0 0 0.35rem 0' }}>
            <strong>Display name</strong> {profile.display_name} <span style={{ color: '#888' }}>(from membership)</span>
          </p>
          {profile.email ? (
            <p style={{ margin: '0 0 0.35rem 0' }}>
              <strong>Email</strong> {profile.email}
            </p>
          ) : null}
          <p style={{ margin: '0 0 0.35rem 0' }}>
            <strong>Entry type</strong> {profile.entry_type}
          </p>
          {isAdminMode ? null : (
            <p style={{ margin: 0 }}>
              <strong>Directory opt-in</strong> {profile.opted_in ? 'Yes' : 'No'}{' '}
              <span style={{ color: '#888' }}>(contact NaBA to change)</span>
            </p>
          )}
          {!isAdminMode && profile.badges_csv ? (
            <p style={{ margin: '0.5rem 0 0 0' }}>
              <strong>Badges</strong> {profile.badges_csv}
            </p>
          ) : null}
        </section>
      ) : null}

      {profile ? (
        <section
          style={{
            marginTop: '1.25rem',
            padding: '1rem 1.25rem',
            border: '1px solid #e5e5e5',
            borderRadius: '0.5rem',
          }}
        >
          <h2 style={{ margin: '0 0 0.5rem 0', fontSize: '1.1rem' }}>Membership</h2>
          <p style={{ margin: '0 0 0.85rem 0', fontSize: '0.95rem', color: '#333' }}>
            Overall status:{' '}
            <span
              style={{
                fontWeight: 600,
                color:
                  (profile.membership_status || '').toLowerCase() === 'active'
                    ? '#166534'
                    : (profile.membership_status || '').toLowerCase() === 'expired'
                      ? '#9a3412'
                      : '#555',
              }}
            >
              {formatMembershipStatus(profile.membership_status)}
            </span>
          </p>
          {(profile.subscriptions || []).length > 0 ? (
            <ul style={{ listStyle: 'none', margin: 0, padding: 0 }}>
              {(profile.subscriptions || []).map((sub, idx) => {
                const current = subscriptionIsCurrent(sub);
                return (
                  <li
                    key={`${sub.subscription_id || sub.membership_id || 'sub'}-${idx}`}
                    style={{
                      padding: '0.75rem 0',
                      borderTop: idx === 0 ? '1px solid #eee' : undefined,
                      borderBottom: '1px solid #eee',
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', gap: '1rem', flexWrap: 'wrap' }}>
                      <div>
                        <div style={{ fontWeight: 600, color: '#222' }}>{sub.title}</div>
                        <div style={{ marginTop: '0.25rem', fontSize: '0.9rem', color: '#555' }}>
                          {formatExpiryLabel(sub)}
                          {sub.period && sub.period_type
                            ? ` · billed every ${sub.period} ${sub.period_type}`
                            : null}
                        </div>
                      </div>
                      <span
                        style={{
                          alignSelf: 'flex-start',
                          fontSize: '0.8rem',
                          fontWeight: 600,
                          padding: '0.2rem 0.55rem',
                          borderRadius: '0.25rem',
                          background: current ? '#dcfce7' : '#f3f4f6',
                          color: current ? '#166534' : '#4b5563',
                        }}
                      >
                        {formatSubscriptionStatus(sub.status)}
                      </span>
                    </div>
                  </li>
                );
              })}
            </ul>
          ) : (
            <p style={{ margin: 0, fontSize: '0.9rem', color: '#666' }}>
              No subscription records are available yet. After the next WordPress sync, membership
              plans and expiration dates will appear here.
            </p>
          )}
          {(profile.membership_status || '').toLowerCase() !== 'active' ? (
            <p style={{ margin: '0.85rem 0 0 0', fontSize: '0.9rem' }}>
              <a href={getJoinMembershipUrl()} style={{ color: '#0057b8' }}>
                Renew or join membership
              </a>
            </p>
          ) : null}
        </section>
      ) : null}

      <section style={{ marginTop: '1.5rem' }}>
        <h2 style={{ fontSize: '1.1rem', marginBottom: '0.75rem' }}>Logo / profile picture</h2>
        {profile?.logo_url ? (
          <img
            src={mediaUrl(profile.logo_url)}
            alt=""
            width={120}
            height={120}
            style={{ objectFit: 'contain', border: '1px solid #e5e5e5', borderRadius: '0.5rem', background: '#fff' }}
          />
        ) : (
          <p style={{ color: '#777', fontSize: '0.9rem' }}>No logo yet.</p>
        )}
        <label style={{ display: 'block', marginTop: '0.75rem' }}>
          <span style={{ ...labelStyle }}>Upload from your computer (JPEG, PNG, GIF, WebP)</span>
          <input
            type="file"
            accept="image/jpeg,image/png,image/gif,image/webp"
            disabled={uploadingLogo || savingLogoUrl}
            onChange={(e) => void onLogoChange(e.target.files)}
          />
        </label>
        {uploadingLogo ? <p style={{ fontSize: '0.85rem', color: '#666' }}>Uploading…</p> : null}

        <form onSubmit={saveLogoFromUrl} style={{ marginTop: '1rem' }}>
          <label style={{ display: 'block' }}>
            <span style={labelStyle}>Or use an image URL</span>
            <input
              type="url"
              style={inputStyle}
              value={logoUrlInput}
              onChange={(e) => setLogoUrlInput(e.target.value)}
              placeholder="https://example.com/logo.png"
              disabled={uploadingLogo || savingLogoUrl}
            />
          </label>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem', marginTop: '0.65rem' }}>
            <button
              type="submit"
              disabled={uploadingLogo || savingLogoUrl}
              style={{
                padding: '0.45rem 1rem',
                borderRadius: '999px',
                border: 'none',
                background: savingLogoUrl ? '#888' : '#333',
                color: '#fff',
                fontWeight: 600,
                cursor: savingLogoUrl ? 'not-allowed' : 'pointer',
              }}
            >
              {savingLogoUrl ? 'Saving…' : 'Use URL'}
            </button>
            {profile?.logo_url ? (
              <button
                type="button"
                onClick={() => void clearLogoUrl()}
                disabled={uploadingLogo || savingLogoUrl}
                style={{
                  padding: '0.45rem 1rem',
                  borderRadius: '999px',
                  border: '1px solid #ccc',
                  background: '#fff',
                  color: '#333',
                  cursor: 'pointer',
                }}
              >
                Clear logo
              </button>
            ) : null}
          </div>
        </form>
      </section>

      {isAdminMode && profile ? (
        <BusinessTeamAdmin profileId={profile.id} entryType={profile.entry_type} />
      ) : null}

      {!isAdminMode ? (
      <section style={{ marginTop: '1.75rem' }}>
        <h2 style={{ fontSize: '1.1rem', marginBottom: '0.75rem' }}>Your businesses</h2>
        {businesses.length === 0 ? (
          <p style={{ color: '#777', fontSize: '0.9rem' }}>No linked businesses you can edit.</p>
        ) : (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
            {businesses.map((b) => (
              <button
                type="button"
                key={b.business_id}
                onClick={() => void loadBusinessProfile(b.business_id)}
                style={{
                  border: '1px solid #ddd',
                  borderRadius: '0.5rem',
                  background: selectedBusinessId === b.business_id ? '#eef2ff' : '#fff',
                  padding: '0.45rem 0.7rem',
                  cursor: 'pointer',
                }}
              >
                Edit {b.display_name}
              </button>
            ))}
          </div>
        )}
        {businessProfile ? (
          <form onSubmit={saveBusinessProfile} style={{ marginTop: '1rem', padding: '1rem', border: '1px solid #eee', borderRadius: '0.5rem' }}>
            <p style={{ marginTop: 0, fontWeight: 600 }}>{businessProfile.display_name}</p>
            <label style={{ display: 'block', marginBottom: '0.75rem' }}>
              <span style={labelStyle}>Organization</span>
              <input
                style={inputStyle}
                value={businessProfile.organization ?? ''}
                onChange={(e) => setBusinessProfile({ ...businessProfile, organization: e.target.value })}
              />
            </label>
            <label style={{ display: 'block', marginBottom: '0.75rem' }}>
              <span style={labelStyle}>Website URL</span>
              <input
                style={inputStyle}
                value={typeof businessProfile.website_url === 'string' ? businessProfile.website_url : ''}
                onChange={(e) => setBusinessProfile({ ...businessProfile, website_url: e.target.value })}
              />
            </label>
            <label style={{ display: 'block', marginBottom: '0.75rem' }}>
              <span style={labelStyle}>Phone</span>
              <input
                style={inputStyle}
                value={businessProfile.phone ?? ''}
                onChange={(e) => setBusinessProfile({ ...businessProfile, phone: e.target.value })}
              />
            </label>
            <label style={{ display: 'block', marginBottom: '0.75rem' }}>
              <span style={labelStyle}>Bio</span>
              <textarea
                style={{ ...inputStyle, minHeight: '90px' }}
                value={businessProfile.bio ?? ''}
                onChange={(e) => setBusinessProfile({ ...businessProfile, bio: e.target.value })}
              />
            </label>
            <button
              type="submit"
              disabled={savingBusiness}
              style={{ padding: '0.5rem 1rem', borderRadius: '999px', border: 'none', background: '#333', color: '#fff' }}
            >
              {savingBusiness ? 'Saving…' : 'Save business profile'}
            </button>
          </form>
        ) : null}
      </section>
      ) : null}

      <section style={{ marginTop: '1.5rem' }}>
        <h2 style={{ fontSize: '1.1rem', marginBottom: '0.75rem' }}>Gallery</h2>
        {profile?.gallery && profile.gallery.length > 0 ? (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
            {profile.gallery.map((u) => (
              <img
                key={u}
                src={mediaUrl(u)}
                alt=""
                width={100}
                height={100}
                style={{ objectFit: 'cover', borderRadius: '0.35rem', border: '1px solid #eee' }}
              />
            ))}
          </div>
        ) : (
          <p style={{ color: '#777', fontSize: '0.9rem' }}>No gallery images yet.</p>
        )}
        <label style={{ display: 'block', marginTop: '0.75rem' }}>
          <span style={labelStyle}>Add images</span>
          <input
            type="file"
            accept="image/jpeg,image/png,image/gif,image/webp"
            multiple
            disabled={uploadingGallery}
            onChange={(e) => void onGalleryChange(e.target.files)}
          />
        </label>
        {uploadingGallery ? <p style={{ fontSize: '0.85rem', color: '#666' }}>Uploading…</p> : null}
      </section>

      <form onSubmit={saveProfile} style={{ marginTop: '2rem' }}>
        <h2 style={{ fontSize: '1.1rem', marginBottom: '1rem' }}>Profile text</h2>

        {isAdminMode ? (
          <fieldset style={{ border: '1px solid #e0e0e0', borderRadius: '0.5rem', padding: '1rem', marginBottom: '1rem' }}>
            <legend style={{ fontSize: '0.9rem', fontWeight: 600 }}>Admin fields</legend>
            <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.75rem' }}>
              <input type="checkbox" checked={optedIn} onChange={(e) => setOptedIn(e.target.checked)} />
              Directory opt-in
            </label>
            <label style={{ display: 'block', marginBottom: '0.75rem' }}>
              <span style={labelStyle}>Entry type</span>
              <select style={inputStyle} value={entryType} onChange={(e) => setEntryType(e.target.value)}>
                <option value="individual">individual</option>
                <option value="organization">organization</option>
                <option value="business">business</option>
              </select>
            </label>
            <label style={{ display: 'block', marginBottom: 0 }}>
              <span style={labelStyle}>Badges (comma-separated)</span>
              <input
                style={inputStyle}
                value={badgesCsv}
                onChange={(e) => setBadgesCsv(e.target.value)}
                placeholder="board, staff"
              />
            </label>
          </fieldset>
        ) : null}

        <label style={{ display: 'block', marginBottom: '1rem' }}>
          <span style={labelStyle}>Organization</span>
          <input style={inputStyle} value={organization} onChange={(e) => setOrganization(e.target.value)} />
        </label>

        <label style={{ display: 'block', marginBottom: '1rem' }}>
          <span style={labelStyle}>Bio</span>
          <textarea
            style={{ ...inputStyle, minHeight: '120px', resize: 'vertical' }}
            value={bio}
            onChange={(e) => setBio(e.target.value)}
          />
        </label>

        <label style={{ display: 'block', marginBottom: '1rem' }}>
          <span style={labelStyle}>Website URL</span>
          <input
            type="url"
            style={inputStyle}
            value={websiteUrl}
            onChange={(e) => setWebsiteUrl(e.target.value)}
            placeholder="https://"
          />
        </label>

        <label style={{ display: 'block', marginBottom: '1rem' }}>
          <span style={labelStyle}>Phone</span>
          <input style={inputStyle} value={phone} onChange={(e) => setPhone(e.target.value)} />
        </label>

        <label style={{ display: 'block', marginBottom: '1rem' }}>
          <span style={labelStyle}>Social links (JSON)</span>
          <textarea
            style={{ ...inputStyle, minHeight: '88px', fontFamily: 'ui-monospace, monospace', fontSize: '0.85rem' }}
            value={socialJson}
            onChange={(e) => setSocialJson(e.target.value)}
            placeholder='{"instagram": "https://instagram.com/..."}'
          />
        </label>

        <label style={{ display: 'block', marginBottom: '1rem' }}>
          <span style={labelStyle}>Services (comma-separated)</span>
          <input style={inputStyle} value={servicesCsv} onChange={(e) => setServicesCsv(e.target.value)} />
        </label>

        <label style={{ display: 'block', marginBottom: '1rem' }}>
          <span style={labelStyle}>Regions (comma-separated)</span>
          <input style={inputStyle} value={regionsCsv} onChange={(e) => setRegionsCsv(e.target.value)} />
        </label>

        <label style={{ display: 'block', marginBottom: '1rem' }}>
          <span style={labelStyle}>Tags (comma-separated)</span>
          <input style={inputStyle} value={tagsCsv} onChange={(e) => setTagsCsv(e.target.value)} />
        </label>

        <fieldset style={{ border: '1px solid #e0e0e0', borderRadius: '0.5rem', padding: '1rem', marginBottom: '1rem' }}>
          <legend style={{ fontSize: '0.9rem', fontWeight: 600 }}>Categories</legend>
          {CATEGORY_OPTIONS.map((opt) => (
            <label key={opt.value} style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.45rem' }}>
              <input
                type="checkbox"
                checked={categories.includes(opt.value)}
                onChange={() => toggleSelected(opt.value, categories, setCategories)}
              />
              {opt.label}
            </label>
          ))}
        </fieldset>

        <fieldset style={{ border: '1px solid #e0e0e0', borderRadius: '0.5rem', padding: '1rem', marginBottom: '1.25rem' }}>
          <legend style={{ fontSize: '0.9rem', fontWeight: 600 }}>Materials</legend>
          {MATERIAL_OPTIONS.map((opt) => (
            <label key={opt.value} style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.45rem' }}>
              <input
                type="checkbox"
                checked={materials.includes(opt.value)}
                onChange={() => toggleSelected(opt.value, materials, setMaterials)}
              />
              {opt.label}
            </label>
          ))}
        </fieldset>

        <fieldset style={{ border: '1px solid #e0e0e0', borderRadius: '0.5rem', padding: '1rem', marginBottom: '1.25rem' }}>
          <legend style={{ fontSize: '0.9rem', fontWeight: 600 }}>Privacy</legend>
          <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.5rem' }}>
            <input type="checkbox" checked={showCity} onChange={(e) => setShowCity(e.target.checked)} />
            Show city / location in the directory
          </label>
          <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.5rem' }}>
            <input type="checkbox" checked={showMemberSince} onChange={(e) => setShowMemberSince(e.target.checked)} />
            Show member since year
          </label>
          <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <input type="checkbox" checked={allowConnect} onChange={(e) => setAllowConnect(e.target.checked)} />
            Allow “Connect” outreach (when enabled on the site)
          </label>
        </fieldset>

        {err ? (
          <p
            role="alert"
            style={{
              color: '#b91c1c',
              background: '#fef2f2',
              padding: '0.75rem 1rem',
              borderRadius: '0.5rem',
              fontSize: '0.9rem',
              marginBottom: '1rem',
            }}
          >
            {err}
          </p>
        ) : null}
        {message ? (
          <p
            role="status"
            style={{
              color: '#166534',
              background: '#f0fdf4',
              padding: '0.75rem 1rem',
              borderRadius: '0.5rem',
              fontSize: '0.9rem',
              marginBottom: '1rem',
            }}
          >
            {message}
          </p>
        ) : null}

        <button
          type="submit"
          disabled={saving}
          style={{
            padding: '0.65rem 1.5rem',
            fontSize: '1rem',
            fontWeight: 600,
            color: '#fff',
            background: saving ? '#888' : '#333',
            border: 'none',
            borderRadius: '999px',
            cursor: saving ? 'not-allowed' : 'pointer',
          }}
        >
          {saving ? 'Saving…' : 'Save profile'}
        </button>
      </form>
    </main>
  );
}
