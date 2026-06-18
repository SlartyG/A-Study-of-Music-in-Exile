"use client";
import { useEffect, useRef, useState } from "react";
import type { ArtistMeta } from "@/lib/data";
import { fmtDelta, sigNote, deltaColor } from "@/lib/format";

interface Props {
  artist: ArtistMeta;
  onClick: () => void;
}

const AVATAR_PALETTE: Array<{ bg: string; fg: string }> = [
  { bg: "#C8B8A0", fg: "#3A2010" },
  { bg: "#A8B8C0", fg: "#1A2A30" },
  { bg: "#B8C0A8", fg: "#2A3020" },
  { bg: "#C0A8B8", fg: "#3A1A28" },
  { bg: "#B4A8B0", fg: "#2A1A28" },
  { bg: "#A8C0B8", fg: "#1A3028" },
  { bg: "#C4B0A4", fg: "#3A2418" },
  { bg: "#B0B4C0", fg: "#1E2030" },
];

const COUNTRY_FLAGS: Record<string, string> = {
  Литва: "🇱🇹",
  Великобритания: "🇬🇧",
  Израиль: "🇮🇱",
  Франция: "🇫🇷",
  Греция: "🇬🇷",
  Грузия: "🇬🇪",
  Турция: "🇹🇷",
  ОАЭ: "🇦🇪",
  США: "🇺🇸",
  Германия: "🇩🇪",
  Сербия: "🇷🇸",
  Армения: "🇦🇲",
  Казахстан: "🇰🇿",
  Финляндия: "🇫🇮",
  Нидерланды: "🇳🇱",
  Австрия: "🇦🇹",
  Польша: "🇵🇱",
};

function countryFlag(country?: string): string {
  if (!country) return "";
  return COUNTRY_FLAGS[country] ?? "🌍";
}

function nameHash(s: string): number {
  let h = 0;
  for (let i = 0; i < s.length; i++) {
    h = s.charCodeAt(i) + ((h << 5) - h);
    h |= 0;
  }
  return Math.abs(h);
}

function Initials({ name }: { name: string }) {
  const parts = name.split(/\s+/);
  const initials =
    parts.length >= 2
      ? parts[0][0].toUpperCase() + parts[parts.length - 1][0].toUpperCase()
      : name.slice(0, 2).toUpperCase();
  const { bg, fg } = AVATAR_PALETTE[nameHash(name) % AVATAR_PALETTE.length];
  return (
    <div
      className="artist-card__media"
      style={{
        width: "100%",
        height: 170,
        background: bg,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        fontSize: "46px",
        fontFamily: "var(--font-heading)",
        fontWeight: 700,
        color: fg,
        letterSpacing: "0.06em",
        borderBottom: "1px solid var(--grid)",
        flexShrink: 0,
      }}
      aria-hidden
    >
      {initials}
    </div>
  );
}

function ArtistPhoto({ name, photo }: { name: string; photo?: string }) {
  const [imgOk, setImgOk] = useState(!!photo);
  if (photo && imgOk) {
    return (
      <div
        className="artist-card__media"
        style={{
          width: "100%",
          height: 170,
          overflow: "hidden",
          flexShrink: 0,
          borderBottom: "1px solid var(--grid)",
          background: "var(--paper-dark)",
        }}
        aria-hidden
      >
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={photo}
          alt=""
          onError={() => setImgOk(false)}
          style={{
            width: "100%",
            height: "100%",
            objectFit: "cover",
            objectPosition: "center top",
            filter: "grayscale(30%) contrast(1.05)",
          }}
        />
      </div>
    );
  }
  return <Initials name={name} />;
}

export default function ArtistCard({ artist, onClick }: Props) {
  const [visible, setVisible] = useState(false);
  const [stampPopped, setStampPopped] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const obs = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setVisible(true);
          if (artist.has_ops) {
            setTimeout(() => setStampPopped(true), 400);
          }
          obs.disconnect();
        }
      },
      { threshold: 0.1 }
    );
    if (ref.current) obs.observe(ref.current);
    return () => obs.disconnect();
  }, [artist.has_ops]);

  const delta = artist.lex.delta;
  const sig = artist.lex.significant;

  return (
    <article
      ref={ref}
      className="artist-card"
      onClick={onClick}
      style={{
        width: "100%",
        maxWidth: 280,
        minHeight: 340,
        flexShrink: 0,
        background: "var(--paper)",
        border: "1px solid var(--grid)",
        boxShadow: "var(--shadow-card)",
        borderRadius: 2,
        cursor: "pointer",
        transition: "transform 200ms ease-out, box-shadow 200ms ease-out",
        opacity: visible ? 1 : 0,
        transform: visible ? "none" : "translateY(24px)",
        display: "flex",
        flexDirection: "column",
        overflow: "hidden",
        position: "relative",
      }}
      onMouseEnter={(e) => {
        (e.currentTarget as HTMLElement).style.transform = "translateY(-4px)";
        (e.currentTarget as HTMLElement).style.boxShadow =
          "4px 6px 20px rgba(60,40,20,0.28)";
      }}
      onMouseLeave={(e) => {
        (e.currentTarget as HTMLElement).style.transform = "none";
        (e.currentTarget as HTMLElement).style.boxShadow = "var(--shadow-card)";
      }}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => e.key === "Enter" && onClick()}
      aria-label={`Открыть карточку: ${artist.display_name}`}
    >
      <ArtistPhoto name={artist.real_name} photo={artist.photo} />

      {/* Stamp — absolute overlay, does not shift layout */}
      {artist.has_ops && (
        <span
          className="stamp"
          style={{
            position: "absolute",
            top: 158,
            right: 10,
            zIndex: 6,
            transform: stampPopped
              ? "rotate(-14deg) scale(1)"
              : "rotate(-14deg) scale(1.3)",
            transition: "transform 200ms ease-out",
            pointerEvents: "none",
          }}
        >
          {artist.ops_label}
        </span>
      )}

      <div className="artist-card__body" style={{ padding: "14px 16px 16px", flexGrow: 1 }}>

        {/* Name */}
        <div
          className="artist-card__name"
          style={{
            fontFamily: "var(--font-heading)",
            fontSize: "20px",
            fontWeight: 700,
            color: "var(--ink)",
            lineHeight: 1.15,
          }}
        >
          {artist.display_name}
        </div>
        <div
          className="artist-card__real-name"
          style={{
            fontFamily: "var(--font-body)",
            fontStyle: "italic",
            fontSize: "13px",
            color: "var(--fog)",
            marginTop: 2,
          }}
        >
          {artist.real_name !== artist.display_name ? artist.real_name : ""}
        </div>

        <div className="artist-card__meta" style={{ marginTop: 12, display: "flex", flexDirection: "column", gap: 3 }}>
          <div
            style={{
              fontFamily: "var(--font-mono)",
              fontSize: "11px",
              color: "var(--ash)",
            }}
          >
            Уехал: {artist.reloc_date || "—"}
          </div>
          <div
            style={{
              fontFamily: "var(--font-mono)",
              fontSize: "11px",
              color: "var(--ash)",
            }}
          >
            {countryFlag(artist.country)}{" "}{artist.country || "—"}
          </div>
        </div>

        <div
          className="artist-card__stats"
          style={{
            marginTop: 14,
            paddingTop: 12,
            borderTop: "1px solid var(--grid)",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "baseline",
          }}
        >
          <div
            style={{
              fontFamily: "var(--font-ui)",
              fontSize: "11px",
              color: "var(--fog)",
            }}
          >
            Треков: {artist.n} до / {artist.n} после
          </div>
          <div
            style={{
              fontFamily: "var(--font-mono)",
              fontSize: "12px",
              color: delta != null ? deltaColor(delta) : "var(--fog)",
              fontWeight: 500,
            }}
          >
            {delta != null ? fmtDelta(delta) : "—"}
            <span
              style={{
                color: sig ? "var(--stamp-amber)" : "var(--fog)",
                marginLeft: 3,
              }}
            >
              {sig ? "*" : "n.s."}
            </span>
          </div>
        </div>
      </div>
    </article>
  );
}
