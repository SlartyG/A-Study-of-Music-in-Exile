"use client";
import { useState } from "react";
import type { Topic } from "@/lib/data";
import { colors } from "@/lib/colors";

interface Props {
  topics: Topic[];
}

export default function DivergingBar({ topics }: Props) {
  const [hoveredId, setHoveredId] = useState<number | null>(null);

  const sorted = [...topics].sort((a, b) => b.delta - a.delta);
  const maxAbs = Math.max(...topics.map((t) => Math.abs(t.delta)));

  const W = 580;
  const rowH = 36;
  const H = sorted.length * rowH + 60;
  // Left margin holds topic name labels
  const margin = { left: 192, right: 80, top: 24, bottom: 36 };
  const plotW = W - margin.left - margin.right;
  const half = plotW / 2;

  const scaleBar = (v: number) => (Math.abs(v) / maxAbs) * half;

  const hovered = hoveredId != null ? topics.find((t) => t.topic_id === hoveredId) : null;

  function truncate(s: string, max: number): string {
    return s.length > max ? s.slice(0, max - 1) + "…" : s;
  }

  return (
    <div className="chart-wrap" style={{ position: "relative" }}>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        width="100%"
        preserveAspectRatio="xMidYMid meet"
        style={{ background: colors.paper, display: "block", overflow: "hidden" }}
        role="img"
        aria-label="Изменение доли тем после отъезда"
      >
        <g transform={`translate(${margin.left},${margin.top})`}>
          {/* Zero line */}
          <line
            x1={half}
            y1={0}
            x2={half}
            y2={H - margin.top - margin.bottom}
            stroke={colors.ash}
            strokeWidth={1}
            strokeDasharray="4,3"
          />

          {/* Tick labels on x-axis */}
          {[-0.04, -0.02, 0, 0.02, 0.04].map((v) => {
            const x = half + (v / maxAbs) * half;
            return (
              <text
                key={v}
                x={x}
                y={H - margin.top - margin.bottom + 18}
                textAnchor="middle"
                fontFamily="JetBrains Mono, monospace"
                fontSize={9}
                fill={colors.fog}
              >
                {v === 0 ? "0" : (v > 0 ? "+" : "") + v.toFixed(2).replace(".", ",")}
              </text>
            );
          })}

          {sorted.map((t, i) => {
            const cy = i * rowH + rowH / 2;
            const barW = scaleBar(t.delta);
            const isPos = t.delta >= 0;
            const isHov = hoveredId === t.topic_id;

            return (
              <g
                key={t.topic_id}
                onMouseEnter={() => setHoveredId(t.topic_id)}
                onMouseLeave={() => setHoveredId(null)}
                style={{ cursor: "pointer" }}
              >
                {/* Bar */}
                <rect
                  x={isPos ? half : half - barW}
                  y={cy - 7}
                  width={Math.max(barW, 2)}
                  height={14}
                  fill={isPos ? colors.before : colors.stampRed}
                  fillOpacity={isHov ? 0.9 : 0.65}
                  rx={1}
                />

                {/* Topic name — in left margin, right-aligned to plot edge */}
                <text
                  x={-10}
                  y={cy + 4}
                  textAnchor="end"
                  fontFamily="var(--font-ui)"
                  fontSize={isHov ? 12 : 11}
                  fontWeight={isHov ? 600 : 400}
                  fill={isHov ? colors.ink : colors.ash}
                >
                  {truncate(t.name, 20)}
                </text>

                {/* Delta value — at far end of bar */}
                <text
                  x={isPos ? half + barW + 5 : half - barW - 5}
                  y={cy + 4}
                  textAnchor={isPos ? "start" : "end"}
                  fontFamily="JetBrains Mono, monospace"
                  fontSize={10}
                  fill={isPos ? colors.before : colors.stampRed}
                >
                  {isPos ? "+" : ""}
                  {(t.delta * 100).toFixed(1).replace(".", ",")}%
                </text>
              </g>
            );
          })}
        </g>
      </svg>

      {/* Hover tooltip */}
      {hovered && (
        <div
          style={{
            position: "absolute",
            bottom: 40,
            right: 0,
            background: colors.black,
            color: "#F5F5F5",
            padding: "10px 14px",
            borderRadius: 2,
            fontFamily: "var(--font-mono)",
            fontSize: "12px",
            maxWidth: 240,
            lineHeight: 1.5,
            boxShadow: "0 4px 12px rgba(0,0,0,0.3)",
            zIndex: 10,
          }}
        >
          <div style={{ fontWeight: 600, marginBottom: 4 }}>{hovered.name}</div>
          <div style={{ color: "rgba(245,245,245,0.6)", fontSize: 11 }}>
            {hovered.top_words.slice(0, 8).join(", ")}
          </div>
          <div
            style={{
              marginTop: 6,
              color: hovered.delta >= 0 ? colors.before : colors.stampRed,
            }}
          >
            {hovered.delta >= 0 ? "+" : ""}
            {(hovered.delta * 100).toFixed(1).replace(".", ",")}% после отъезда
          </div>
        </div>
      )}

      <p
        style={{
          fontFamily: "var(--font-ui)",
          fontSize: "13px",
          color: colors.fog,
          marginTop: 8,
        }}
      >
        Доля каждой темы: среднее по всем трекам периода. Названия тем наша
        интерпретация топ-слов, не машинная маркировка. Наведите для деталей.
      </p>
      <div
        style={{
          fontFamily: "var(--font-mono)",
          fontSize: "12px",
          color: colors.ash,
          marginTop: 4,
        }}
      >
        χ²-тест: p ≈ 0,008
      </div>
    </div>
  );
}
