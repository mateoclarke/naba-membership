import { useEffect, useMemo, useRef, useState } from "react";
import type L from "leaflet";
import MemberLoginForm from "./MemberLoginForm";
import {
  canAccessMembershipDirectory,
  getJoinMembershipUrl,
  getStoredToken,
} from "../lib/membershipApi";

type MapItem = {
  id: number;
  display_name: string;
  entry_type: "individual" | "organization" | "business" | string;
  role?: string | null;
  organization?: string | null;
  city?: string | null;
  state_province?: string | null;
  country?: string | null;
  location_display?: string | null;
  slug?: string | null;
  latitude: number;
  longitude: number;
};

interface MapProps {
  apiBaseUrl: string;
  stateMapping: Record<string, string>;
}

type AccessPhase = "checking" | "allowed" | "guest" | "inactive";

function businessPath(item: MapItem): string {
  if (item.slug && String(item.slug).trim()) {
    return `/directory/business/${encodeURIComponent(String(item.slug).trim())}`;
  }
  const nameSlug =
    (item.display_name || "")
      .toLowerCase()
      .trim()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "") || "member";
  return `/directory/business/${encodeURIComponent(`${nameSlug}-${item.id}`)}`;
}

function profileLink(item: MapItem): string {
  if (item.entry_type === "business") return businessPath(item);
  return "/directory?view=members";
}

function markerColor(entryType: string): string {
  if (entryType === "business") return "#1d4ed8";
  if (entryType === "organization") return "#7c3aed";
  return "#15803d";
}

function MapGate({ phase }: { phase: "guest" | "inactive" }) {
  const inactive = phase === "inactive";
  return (
    <main style={{ maxWidth: 480, margin: "2rem auto", padding: "0 1.5rem" }}>
      <div
        style={{
          padding: "1.5rem",
          border: "1px solid #e0e0e0",
          borderRadius: "0.75rem",
          background: "#fafafa",
          marginBottom: inactive ? 0 : "1.25rem",
        }}
      >
        <h1 style={{ margin: "0 0 0.5rem 0", fontSize: "1.35rem" }}>
          {inactive ? "Membership renewal needed" : "Members only"}
        </h1>
        <p style={{ margin: 0, color: "#555", lineHeight: 1.5, fontSize: "0.95rem" }}>
          {inactive
            ? "You are signed in, but your membership is not currently active. Renew to view the member map."
            : "Sign in with an active NaBA membership to view the interactive member map."}
        </p>
        <p style={{ margin: "1rem 0 0 0" }}>
          <a
            href={getJoinMembershipUrl()}
            target="_blank"
            rel="noreferrer"
            style={{
              display: "inline-block",
              padding: "0.55rem 1.25rem",
              borderRadius: 999,
              background: "#166534",
              color: "#fff",
              textDecoration: "none",
              fontWeight: 600,
              fontSize: "0.95rem",
            }}
          >
            {inactive ? "Renew your membership" : "Join as a member"}
          </a>
        </p>
      </div>
      {!inactive ? <MemberLoginForm redirectTo="/map" compact /> : null}
    </main>
  );
}

export default function Map({ apiBaseUrl, stateMapping }: MapProps) {
  const mapRef = useRef<L.Map | null>(null);
  const markersLayerRef = useRef<L.LayerGroup | null>(null);
  const geojsonRef = useRef<L.GeoJSON | null>(null);
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const [access, setAccess] = useState<AccessPhase>("checking");
  const [items, setItems] = useState<MapItem[]>([]);
  const [selectedState, setSelectedState] = useState<string>("");
  const [selectedCountry, setSelectedCountry] = useState<string>("");
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    if (canAccessMembershipDirectory()) {
      setAccess("allowed");
      return;
    }
    setAccess(getStoredToken() ? "inactive" : "guest");
  }, []);

  const stateCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const item of items) {
      if ((item.country || "").toUpperCase() !== "US") continue;
      const st = (item.state_province || "").trim().toUpperCase();
      if (!st) continue;
      counts[st] = (counts[st] || 0) + 1;
    }
    return counts;
  }, [items]);

  const countries = useMemo(() => {
    const map: Record<string, number> = {};
    for (const item of items) {
      const country = (item.country || "").trim();
      if (!country || country.toUpperCase() === "US") continue;
      map[country] = (map[country] || 0) + 1;
    }
    return Object.entries(map).sort((a, b) => b[1] - a[1]);
  }, [items]);

  const filteredItems = useMemo(() => {
    return items.filter((item) => {
      const country = (item.country || "").toUpperCase();
      const state = (item.state_province || "").toUpperCase();
      if (selectedState) return country === "US" && state === selectedState;
      if (selectedCountry) return (item.country || "") === selectedCountry;
      return true;
    });
  }, [items, selectedState, selectedCountry]);

  useEffect(() => {
    if (access !== "allowed") return;
    const params = new URLSearchParams(window.location.search);
    const state = (params.get("state") || "").toUpperCase();
    if (state) setSelectedState(state);
  }, [access]);

  useEffect(() => {
    if (access !== "allowed") {
      setIsLoading(false);
      return;
    }
    const base = (apiBaseUrl || "").replace(/\/$/, "");
    if (!base) {
      setIsLoading(false);
      return;
    }
    const headers: Record<string, string> = {};
    const token = getStoredToken();
    if (token) headers.Authorization = `Bearer ${token}`;

    fetch(`${base}/api/v1/public/members/map`, { headers })
      .then((r) => (r.ok ? r.json() : null))
      .then((payload) => {
        if (!payload || !Array.isArray(payload.items)) return;
        setItems(
          payload.items.filter(
            (x: any) =>
              typeof x.latitude === "number" && typeof x.longitude === "number"
          )
        );
      })
      .catch(() => {})
      .finally(() => setIsLoading(false));
  }, [apiBaseUrl, access]);

  useEffect(() => {
    if (access !== "allowed") return;
    if (!mapContainerRef.current || mapRef.current) return;
    if (typeof (window as any).L === "undefined") return;

    const Lw = (window as any).L;
    const map = Lw.map(mapContainerRef.current).setView([39.8283, -98.5795], 4);
    mapRef.current = map;
    Lw.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 18,
      attribution:
        '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    }).addTo(map);
    markersLayerRef.current = Lw.layerGroup().addTo(map);

    const stateCodeFromFeature = (feature: any): string | null => {
      if (feature?.properties?.STUSPS) return feature.properties.STUSPS;
      const name = feature?.properties?.name || feature?.properties?.NAME;
      if (name && stateMapping[name]) return stateMapping[name];
      return null;
    };

    const stateStyle = (feature: any) => {
      const stateCode = stateCodeFromFeature(feature);
      const count = stateCode ? stateCounts[stateCode] || 0 : 0;
      const isActive = !!stateCode && stateCode === selectedState;
      return {
        fillColor: count ? "#c7d2fe" : "#f3f4f6",
        weight: isActive ? 3 : 1,
        opacity: 1,
        color: isActive ? "#3730a3" : "#d1d5db",
        fillOpacity: isActive ? 0.65 : 0.45,
      };
    };

    fetch(
      "https://raw.githubusercontent.com/PublicaMundi/MappingAPI/master/data/geojson/us-states.json"
    )
      .then((response) => response.json())
      .then((data) => {
        const geojson = Lw.geoJson(data, {
          style: stateStyle,
          onEachFeature: (feature: any, layer: any) => {
            const code = stateCodeFromFeature(feature);
            layer.on("click", () => {
              if (!code) return;
              setSelectedCountry("");
              setSelectedState((prev) => (prev === code ? "" : code));
              map.fitBounds(layer.getBounds());
            });
          },
        }).addTo(map);
        geojsonRef.current = geojson;
      })
      .catch(() => {});

    return () => {
      if (mapRef.current) {
        mapRef.current.remove();
        mapRef.current = null;
      }
      markersLayerRef.current = null;
      geojsonRef.current = null;
    };
  }, [access, selectedState, stateCounts, stateMapping]);

  useEffect(() => {
    if (access !== "allowed") return;
    const map = mapRef.current;
    const Lw = (window as any).L;
    if (!map || !Lw || !markersLayerRef.current) return;

    markersLayerRef.current.clearLayers();
    for (const item of filteredItems) {
      const marker = Lw.circleMarker([item.latitude, item.longitude], {
        radius: 6,
        color: markerColor(item.entry_type),
        fillColor: markerColor(item.entry_type),
        fillOpacity: 0.85,
        weight: 1,
      });
      const details = [item.role, item.location_display].filter(Boolean).join("<br/>");
      marker.bindPopup(
        `<div style="min-width:180px;">
          <strong>${item.display_name}</strong><br/>
          ${details ? `${details}<br/>` : ""}
          <a href="${profileLink(item)}">View profile</a>
        </div>`
      );
      marker.addTo(markersLayerRef.current);
    }

    if (geojsonRef.current) {
      geojsonRef.current.setStyle((feature: any) => {
        const code =
          feature?.properties?.STUSPS ||
          stateMapping[feature?.properties?.name || feature?.properties?.NAME];
        const count = code ? stateCounts[code] || 0 : 0;
        const isActive = !!code && code === selectedState;
        return {
          fillColor: count ? "#c7d2fe" : "#f3f4f6",
          weight: isActive ? 3 : 1,
          opacity: 1,
          color: isActive ? "#3730a3" : "#d1d5db",
          fillOpacity: isActive ? 0.65 : 0.45,
        };
      });
    }

    const url = new URL(window.location.href);
    if (selectedState) url.searchParams.set("state", selectedState);
    else url.searchParams.delete("state");
    window.history.replaceState({}, "", url.toString());
  }, [access, filteredItems, selectedState, stateCounts, stateMapping]);

  if (access === "checking") {
    return (
      <main style={{ maxWidth: 480, margin: "2rem auto", padding: "0 1.5rem", color: "#666" }}>
        Checking access…
      </main>
    );
  }

  if (access === "guest" || access === "inactive") {
    return <MapGate phase={access} />;
  }

  const heading = selectedState
    ? `State: ${selectedState}`
    : selectedCountry
    ? `Country: ${selectedCountry}`
    : "All mapped members";

  return (
    <div style={{ position: "relative" }}>
      <div id="map" ref={mapContainerRef} style={{ width: "100%", height: "100vh" }} />
      <aside
        style={{
          position: "absolute",
          top: 16,
          right: 16,
          width: 360,
          maxHeight: "calc(100vh - 32px)",
          overflowY: "auto",
          background: "rgba(255,255,255,0.96)",
          border: "1px solid #ddd",
          borderRadius: 10,
          padding: 12,
          zIndex: 1000,
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", gap: 8 }}>
          <strong>{heading}</strong>
          {(selectedState || selectedCountry) && (
            <button
              type="button"
              onClick={() => {
                setSelectedState("");
                setSelectedCountry("");
              }}
              style={{ border: "1px solid #ddd", borderRadius: 999, padding: "2px 10px", background: "#fff", cursor: "pointer" }}
            >
              Clear
            </button>
          )}
        </div>
        <p style={{ margin: "8px 0 10px", color: "#666", fontSize: 13 }}>
          {isLoading ? "Loading markers..." : `${filteredItems.length} results`}
        </p>
        {countries.length > 0 && !selectedState && (
          <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 10 }}>
            {countries.map(([country, count]) => (
              <button
                key={country}
                type="button"
                onClick={() => {
                  setSelectedState("");
                  setSelectedCountry(country);
                }}
                style={{
                  border: "1px solid #ddd",
                  borderRadius: 999,
                  padding: "2px 8px",
                  background: selectedCountry === country ? "#111827" : "#fff",
                  color: selectedCountry === country ? "#fff" : "#111827",
                  cursor: "pointer",
                  fontSize: 12,
                }}
              >
                {country} ({count})
              </button>
            ))}
          </div>
        )}
        <div style={{ display: "grid", gap: 8 }}>
          {filteredItems.slice(0, 200).map((item) => (
            <button
              key={item.id}
              type="button"
              onClick={() => {
                if (!mapRef.current) return;
                mapRef.current.setView([item.latitude, item.longitude], 8);
              }}
              style={{
                textAlign: "left",
                border: "1px solid #ececec",
                background: "#fff",
                borderRadius: 8,
                padding: 10,
                cursor: "pointer",
              }}
            >
              <div style={{ fontWeight: 600 }}>{item.display_name}</div>
              <div style={{ fontSize: 13, color: "#666" }}>
                {[item.role, item.location_display].filter(Boolean).join(" - ")}
              </div>
            </button>
          ))}
        </div>
      </aside>
    </div>
  );
}
