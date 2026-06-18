"use client";
import { useState, useMemo } from "react";
import type { ArtistMeta } from "@/lib/data";
import SectionLabel from "@/components/layout/SectionLabel";
import ArtistCard from "./ArtistCard";
import ArtistPanel from "./ArtistPanel";

const COUNTRIES = [
  "Великобритания", "Германия", "Грузия", "Израиль", "Литва",
  "США", "Франция", "Греция", "Сербия", "Армения", "ОАЭ",
  "Турция", "Казахстан", "Португалия",
];

export default function ArtistGrid({ artists }: { artists: ArtistMeta[] }) {
  const [filter, setFilter] = useState<"all" | "ops" | "no-ops">("all");
  const [country, setCountry] = useState<string>("all");
  const [selected, setSelected] = useState<ArtistMeta | null>(null);

  const filtered = useMemo(() => {
    return artists.filter((a) => {
      if (filter === "ops" && !a.has_ops) return false;
      if (filter === "no-ops" && a.has_ops) return false;
      if (country !== "all" && a.country !== country) return false;
      return true;
    });
  }, [artists, filter, country]);

  const FilterBtn = ({
    id,
    label,
  }: {
    id: typeof filter;
    label: string;
  }) => (
    <button
      onClick={() => setFilter(id)}
      style={{
        fontFamily: "var(--font-ui)",
        fontSize: "13px",
        padding: "6px 14px",
        border: "1px solid var(--ash)",
        background: filter === id ? "var(--stamp-amber)" : "var(--paper)",
        color: filter === id ? "var(--ink)" : "var(--ash)",
        cursor: "pointer",
        borderRadius: 2,
        transition: "all 150ms ease-out",
        whiteSpace: "nowrap",
      }}
    >
      {label}
    </button>
  );

  return (
    <section id="artists" className="section">
      <div className="container--wide">
        <SectionLabel section="РАЗДЕЛ 03" title="КАРТОТЕКА" />
        <h2 style={{ marginBottom: 32 }}>Дело ведётся на 21 человека</h2>

        {/* Filters */}
        <div
          style={{
            display: "flex",
            gap: 8,
            flexWrap: "wrap",
            alignItems: "center",
            marginBottom: 36,
          }}
        >
          <FilterBtn id="all" label="Все" />
          <FilterBtn id="ops" label="С особым статусом" />
          <FilterBtn id="no-ops" label="Без статуса" />

          <select
            value={country}
            onChange={(e) => setCountry(e.target.value)}
            style={{
              fontFamily: "var(--font-ui)",
              fontSize: "13px",
              padding: "6px 12px",
              border: "1px solid var(--ash)",
              background: "var(--paper)",
              color: country !== "all" ? "var(--ink)" : "var(--ash)",
              cursor: "pointer",
              borderRadius: 2,
              appearance: "none",
              paddingRight: 28,
            }}
            aria-label="Фильтр по стране"
          >
            <option value="all">▼ По стране</option>
            {COUNTRIES.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </div>

        {/* Cards grid */}
        <div
          className="artist-grid"
          role="list"
          aria-label={`Список артистов (${filtered.length})`}
        >
          {filtered.map((artist) => (
            <div key={artist.pseudonym} role="listitem">
              <ArtistCard
                artist={artist}
                onClick={() => setSelected(artist)}
              />
            </div>
          ))}
        </div>

        {filtered.length === 0 && (
          <p
            style={{
              fontFamily: "var(--font-mono)",
              fontSize: "14px",
              color: "var(--fog)",
              marginTop: 32,
            }}
          >
            Нет артистов, соответствующих фильтру.
          </p>
        )}

        {/* Legend */}
        <div
          style={{
            marginTop: 32,
            fontFamily: "var(--font-ui)",
            fontSize: "12px",
            color: "var(--fog)",
            display: "flex",
            gap: 24,
            flexWrap: "wrap",
          }}
        >
          <span>
            <span style={{ color: "var(--before)" }}>+</span>&nbsp;/&nbsp;
            <span style={{ color: "var(--stamp-red)" }}>−</span>
            &nbsp;— направление Δ тональности
          </span>
          <span>
            <span style={{ color: "var(--stamp-amber)" }}>*</span>
            &nbsp;— p &lt; 0,05 (значимо)
          </span>
          <span>n.s. — не значимо</span>
        </div>
      </div>

      {selected && (
        <ArtistPanel artist={selected} onClose={() => setSelected(null)} />
      )}
    </section>
  );
}
