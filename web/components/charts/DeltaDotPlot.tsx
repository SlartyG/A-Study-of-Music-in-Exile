"use client";
import { useState } from "react";
import type { ArtistMeta } from "@/lib/data";
import { colors } from "@/lib/colors";
import { fmtDelta, fmtP } from "@/lib/format";

interface Props {
  artists: ArtistMeta[];
  onArtistClick?: (artist: ArtistMeta) => void;
}

export default function DeltaDotPlot({ artists, onArtistClick }: Props) {
  const [tooltip, setTooltip] = useState<{
    artist: ArtistMeta;
    x: number;
    y: number;
  } | null>(null);

  const sorted = [...artists]
    .filter((a) => a.lex.delta != null)
    .sort((a, b) => (a.lex.delta ?? 0) - (b.lex.delta ?? 0));

  const W = 540;
  const rowH = 28;
  const H = sorted.length * rowH + 40;
  const margin = { left: 148, right: 80, top: 20, bottom: 24 };
  const plotW = W - margin.left - margin.right;

  const xMin = -0.025;
  const xMax = 0.025;
  const xScale = (v: number) => ((v - xMin) / (xMax - xMin)) * plotW;
  const xZero = xScale(0);

  const tickVals = [-0.02, -0.01, 0, 0.01, 0.02];

  return (
    <div className="chart-wrap" style={{ position: "relative", maxWidth: "100%" }}>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        width="100%"
        preserveAspectRatio="xMidYMid meet"
        style={{ background: colors.paper, display: "block", overflow: "hidden" }}
        role="img"
        aria-label="Дельта тональности по артистам"
      >
        <g transform={`translate(${margin.left},${margin.top})`}>
          {/* Tick lines */}
          {tickVals.map((v) => {
            const x = xScale(v);
            return (
              <g key={v}>
                <line
                  x1={x}
                  y1={0}
                  x2={x}
                  y2={H - margin.top - margin.bottom}
                  stroke={v === 0 ? colors.ash : colors.grid}
                  strokeWidth={v === 0 ? 1 : 1}
                  strokeDasharray={v === 0 ? "4,3" : undefined}
                />
                <text
                  x={x}
                  y={H - margin.top - margin.bottom + 16}
                  textAnchor="middle"
                  fontFamily="JetBrains Mono, monospace"
                  fontSize={9}
                  fill={colors.fog}
                >
                  {v === 0 ? "0" : (v > 0 ? "+" : "") + v.toFixed(2).replace(".", ",")}
                </text>
              </g>
            );
          })}

          {/* Dots and labels */}
          {sorted.map((a, i) => {
            const delta = a.lex.delta ?? 0;
            const cx = xScale(delta);
            const cy = i * rowH + rowH / 2;
            const sig = a.lex.significant;
            const r = sig ? 8 : 5;
            const dotColor =
              Math.abs(delta) < 0.001
                ? colors.fog
                : delta < 0
                ? colors.stampRed
                : colors.before;

            // Diamond shape for ops, circle for others
            const shape = a.has_ops ? (
              <polygon
                points={`${cx},${cy - r} ${cx + r},${cy} ${cx},${cy + r} ${cx - r},${cy}`}
                fill={dotColor}
                stroke={dotColor}
                strokeWidth={1}
                fillOpacity={0.85}
              />
            ) : (
              <circle
                cx={cx}
                cy={cy}
                r={r}
                fill={dotColor}
                fillOpacity={0.85}
                stroke={dotColor}
                strokeWidth={1}
              />
            );

            return (
              <g
                key={a.pseudonym}
                style={{ cursor: "pointer" }}
                onClick={() => onArtistClick?.(a)}
                onMouseEnter={(e) => {
                  const rect = (e.currentTarget as SVGElement)
                    .closest("svg")
                    ?.getBoundingClientRect();
                  setTooltip({
                    artist: a,
                    x: cx + margin.left,
                    y: cy + margin.top,
                  });
                }}
                onMouseLeave={() => setTooltip(null)}
                role="button"
                aria-label={`${a.display_name}: Δ = ${fmtDelta(a.lex.delta)}`}
              >
                {shape}

                {/* Artist label */}
                <text
                  x={-8}
                  y={cy + 4}
                  textAnchor="end"
                  fontFamily="var(--font-ui)"
                  fontSize={sig ? 12 : 11}
                  fontWeight={sig ? 600 : 400}
                  fill={colors.ash}
                >
                  {a.display_name}
                  {a.has_ops ? " *" : ""}
                </text>
              </g>
            );
          })}
        </g>
      </svg>

      {/* Legend */}
      <div
        style={{
          fontFamily: "var(--font-ui)",
          fontSize: "12px",
          color: colors.fog,
          marginTop: 10,
          display: "flex",
          gap: 20,
          flexWrap: "wrap",
        }}
      >
        <span>● — без особого статуса</span>
        <span>◆ — иностранный агент</span>
        <span>Крупнее = p &lt; 0,05</span>
      </div>

      {/* Tooltip */}
      {tooltip && (
        <div
          style={{
            position: "absolute",
            left: `${(tooltip.x / W) * 100}%`,
            top: `${(tooltip.y / H) * 100}%`,
            transform: "translate(-50%, -130%)",
            background: colors.black,
            color: "#F5F5F5",
            padding: "8px 12px",
            borderRadius: 2,
            fontFamily: "var(--font-mono)",
            fontSize: "12px",
            pointerEvents: "none",
            whiteSpace: "nowrap",
            zIndex: 10,
            boxShadow: "0 4px 12px rgba(0,0,0,0.3)",
          }}
        >
          <strong>{tooltip.artist.display_name}</strong>
          <br />
          Δ = {fmtDelta(tooltip.artist.lex.delta)}
          &nbsp;·&nbsp;p = {fmtP(tooltip.artist.lex.p)}
          {tooltip.artist.has_ops && (
            <span style={{ color: colors.stampRed }}>&nbsp;· иноагент</span>
          )}
        </div>
      )}
    </div>
  );
}
