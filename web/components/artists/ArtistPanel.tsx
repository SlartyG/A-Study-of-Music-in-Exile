"use client";
import type { ArtistMeta } from "@/lib/data";
import { fmtDelta, fmtP, deltaColor } from "@/lib/format";

interface Props {
  artist: ArtistMeta | null;
  onClose: () => void;
}

function MiniBar({
  before,
  after,
  label,
}: {
  before: number | null;
  after: number | null;
  label: string;
}) {
  if (before == null || after == null) return null;
  const range = 0.06;
  const toPercent = (v: number) =>
    Math.max(0, Math.min(100, ((v + range / 2) / range) * 100));
  return (
    <div style={{ marginBottom: 16 }}>
      <div
        style={{
          fontFamily: "var(--font-mono)",
          fontSize: "10px",
          color: "var(--fog)",
          letterSpacing: "0.08em",
          marginBottom: 6,
          textTransform: "uppercase",
        }}
      >
        {label}
      </div>
      {[
        { period: "До", value: before, color: "var(--before)" },
        { period: "После", value: after, color: "var(--after)" },
      ].map(({ period, value, color }) => (
        <div
          key={period}
          style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 4 }}
        >
          <div
            style={{
              fontFamily: "var(--font-mono)",
              fontSize: "10px",
              color: "var(--fog)",
              width: 32,
              flexShrink: 0,
            }}
          >
            {period}
          </div>
          <div
            style={{
              height: 8,
              background: color,
              opacity: 0.7,
              width: `${toPercent(value)}%`,
              borderRadius: 1,
              minWidth: 2,
              transition: "width 400ms ease-out",
            }}
          />
          <div
            style={{
              fontFamily: "var(--font-mono)",
              fontSize: "11px",
              color: "var(--typewriter)",
            }}
          >
            {value.toFixed(3).replace(".", ",")}
          </div>
        </div>
      ))}
    </div>
  );
}

function StatRow({ label, value, highlight }: { label: string; value: string; highlight?: boolean }) {
  return (
    <div
      style={{
        display: "flex",
        justifyContent: "space-between",
        padding: "5px 0",
        borderBottom: "1px solid var(--grid)",
      }}
    >
      <span
        style={{
          fontFamily: "var(--font-mono)",
          fontSize: "11px",
          color: "var(--fog)",
          textTransform: "uppercase",
          letterSpacing: "0.06em",
        }}
      >
        {label}
      </span>
      <span
        style={{
          fontFamily: "var(--font-mono)",
          fontSize: "12px",
          color: highlight ? "var(--stamp-amber)" : "var(--typewriter)",
          fontWeight: highlight ? 600 : 400,
        }}
      >
        {value}
      </span>
    </div>
  );
}

export default function ArtistPanel({ artist, onClose }: Props) {
  if (!artist) return null;

  return (
    <>
      {/* Backdrop */}
      <div
        style={{
          position: "fixed",
          inset: 0,
          background: "rgba(13,13,13,0.4)",
          zIndex: 200,
          backdropFilter: "blur(2px)",
        }}
        onClick={onClose}
        aria-hidden
      />

      {/* Panel */}
      <aside
        style={{
          position: "fixed",
          right: 0,
          top: 0,
          bottom: 0,
          width: "min(420px, 100vw)",
          background: "var(--paper)",
          boxShadow: "-4px 0 24px rgba(60,40,20,0.25)",
          zIndex: 201,
          overflowY: "auto",
          padding: "32px 28px",
          display: "flex",
          flexDirection: "column",
          gap: 0,
          animation: "slideIn 300ms ease-out",
        }}
        role="dialog"
        aria-label={`Карточка: ${artist.display_name}`}
      >
        {/* Close */}
        <button
          onClick={onClose}
          style={{
            position: "absolute",
            top: 20,
            right: 20,
            background: "none",
            border: "none",
            fontSize: 24,
            cursor: "pointer",
            color: "var(--fog)",
            lineHeight: 1,
          }}
          aria-label="Закрыть"
        >
          ✕
        </button>

        {/* Header */}
        <div style={{ marginBottom: 24 }}>
          <div
            style={{
              fontFamily: "var(--font-heading)",
              fontSize: "30px",
              fontWeight: 700,
              color: "var(--ink)",
              lineHeight: 1.1,
            }}
          >
            {artist.display_name}
          </div>
          <div
            style={{
              fontFamily: "var(--font-body)",
              fontStyle: "italic",
              fontSize: "14px",
              color: "var(--fog)",
              marginTop: 4,
            }}
          >
            {artist.real_name}
          </div>
          <div
            style={{
              fontFamily: "var(--font-mono)",
              fontSize: "11px",
              color: "var(--fog)",
              marginTop: 6,
            }}
          >
            {[artist.city, artist.country].filter(Boolean).join(", ")}
            {artist.reloc_date ? ` · ${artist.reloc_date}` : ""}
          </div>
          {artist.has_ops && (
            <div style={{ marginTop: 12 }}>
              <span className="stamp">{artist.ops_label}</span>
            </div>
          )}
        </div>

        <hr className="divider" />

        {/* Lexical method */}
        <div style={{ marginBottom: 24 }}>
          <div
            style={{
              fontFamily: "var(--font-mono)",
              fontSize: "11px",
              color: "var(--fog)",
              letterSpacing: "0.1em",
              textTransform: "uppercase",
              marginBottom: 12,
            }}
          >
            Метод 1 / Словарь
          </div>
          <MiniBar
            before={artist.lex.mean_before}
            after={artist.lex.mean_after}
            label="Средняя тональность"
          />
          <StatRow
            label="Δ"
            value={
              artist.lex.delta != null
                ? fmtDelta(artist.lex.delta)
                : "—"
            }
            highlight={artist.lex.significant}
          />
          <StatRow label="p-value" value={fmtP(artist.lex.p)} highlight={artist.lex.significant} />
          <StatRow
            label="Cohen's d"
            value={artist.lex.d != null ? artist.lex.d.toFixed(3).replace(".", ",") : "—"}
          />
        </div>

        <hr className="divider" />

        {/* BERT method */}
        <div style={{ marginBottom: 24 }}>
          <div
            style={{
              fontFamily: "var(--font-mono)",
              fontSize: "11px",
              color: "var(--fog)",
              letterSpacing: "0.1em",
              textTransform: "uppercase",
              marginBottom: 12,
            }}
          >
            Метод 3 / ruBERT
          </div>
          <MiniBar
            before={artist.bert.mean_before}
            after={artist.bert.mean_after}
            label="Средний compound"
          />
          <StatRow
            label="Δ"
            value={artist.bert.delta != null ? fmtDelta(artist.bert.delta) : "—"}
            highlight={artist.bert.significant}
          />
          <StatRow
            label="p-value"
            value={fmtP(artist.bert.p)}
            highlight={artist.bert.significant}
          />
        </div>

        {/* Topics */}
        {(artist.top3_before.length > 0 || artist.top3_after.length > 0) && (
          <>
            <hr className="divider" />
            <div>
              <div
                style={{
                  fontFamily: "var(--font-mono)",
                  fontSize: "11px",
                  color: "var(--fog)",
                  letterSpacing: "0.1em",
                  textTransform: "uppercase",
                  marginBottom: 12,
                }}
              >
                Темы (топ-3)
              </div>
              {[
                { label: "До", items: artist.top3_before },
                { label: "После", items: artist.top3_after },
              ].map(({ label, items }) => (
                <div key={label} style={{ marginBottom: 12 }}>
                  <div
                    style={{
                      fontFamily: "var(--font-mono)",
                      fontSize: "10px",
                      color: "var(--fog)",
                      marginBottom: 6,
                    }}
                  >
                    {label}
                  </div>
                  {items.map((t) => (
                    <div
                      key={t.topic_id}
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: 8,
                        marginBottom: 5,
                      }}
                    >
                      <div
                        style={{
                          height: 6,
                          width: `${Math.round(t.share * 300)}px`,
                          maxWidth: 120,
                          minWidth: 4,
                          background: "var(--typewriter)",
                          opacity: 0.5,
                          borderRadius: 1,
                        }}
                      />
                      <div
                        style={{
                          fontFamily: "var(--font-mono)",
                          fontSize: "11px",
                          color: "var(--ash)",
                        }}
                      >
                        {t.name}
                      </div>
                    </div>
                  ))}
                </div>
              ))}
            </div>
          </>
        )}
      </aside>

      <style>{`
        @keyframes slideIn {
          from { transform: translateX(100%); }
          to { transform: translateX(0); }
        }
      `}</style>
    </>
  );
}
