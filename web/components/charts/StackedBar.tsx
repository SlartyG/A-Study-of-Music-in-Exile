"use client";
import { useState } from "react";
import type { Topic } from "@/lib/data";
import { topicColor } from "@/lib/colors";

interface Props {
  topics: Topic[];
}

export default function StackedBar({ topics }: Props) {
  const [hovered, setHovered] = useState<number | null>(null);

  // Sort topics by topic_id for consistent stacking
  const sorted = [...topics].sort((a, b) => a.topic_id - b.topic_id);

  const W = 320;
  const H = 280;
  const barW = 80;
  const gap = 60;
  const leftBar = 40;
  const rightBar = leftBar + barW + gap;

  const before_total = sorted.reduce((s, t) => s + t.share_before, 0) || 1;
  const after_total = sorted.reduce((s, t) => s + t.share_after, 0) || 1;

  function buildSegments(values: number[], total: number) {
    let y = 0;
    return sorted.map((t, i) => {
      const h = (values[i] / total) * H;
      const seg = { y, h, topic_id: t.topic_id, name: t.name };
      y += h;
      return seg;
    });
  }

  const beforeSegs = buildSegments(
    sorted.map((t) => t.share_before),
    before_total
  );
  const afterSegs = buildSegments(
    sorted.map((t) => t.share_after),
    after_total
  );

  return (
    <div className="chart-wrap" style={{ position: "relative" }}>
      <svg
        viewBox={`0 0 ${W + 140} ${H + 60}`}
        width="100%"
        preserveAspectRatio="xMidYMid meet"
        style={{ maxWidth: W + 140, display: "block" }}
        role="img"
        aria-label="Тематическая структура текстов до и после отъезда"
      >
        <g transform="translate(0, 20)">
          {/* Before bar */}
          {beforeSegs.map((seg) => {
            const isHov = hovered === seg.topic_id;
            return (
              <rect
                key={seg.topic_id}
                x={leftBar}
                y={seg.y}
                width={barW}
                height={Math.max(seg.h, 1)}
                fill={topicColor(seg.topic_id)}
                fillOpacity={hovered == null || isHov ? 0.85 : 0.35}
                stroke="var(--paper)"
                strokeWidth={0.5}
                style={{ cursor: "pointer", transition: "fill-opacity 150ms" }}
                onMouseEnter={() => setHovered(seg.topic_id)}
                onMouseLeave={() => setHovered(null)}
              />
            );
          })}

          {/* After bar */}
          {afterSegs.map((seg) => {
            const isHov = hovered === seg.topic_id;
            return (
              <rect
                key={seg.topic_id}
                x={rightBar}
                y={seg.y}
                width={barW}
                height={Math.max(seg.h, 1)}
                fill={topicColor(seg.topic_id)}
                fillOpacity={hovered == null || isHov ? 0.85 : 0.35}
                stroke="var(--paper)"
                strokeWidth={0.5}
                style={{ cursor: "pointer", transition: "fill-opacity 150ms" }}
                onMouseEnter={() => setHovered(seg.topic_id)}
                onMouseLeave={() => setHovered(null)}
              />
            );
          })}

          {/* Connecting lines for hovered segment */}
          {hovered != null && (() => {
            const bs = beforeSegs.find((s) => s.topic_id === hovered);
            const as_ = afterSegs.find((s) => s.topic_id === hovered);
            if (!bs || !as_) return null;
            return (
              <g opacity={0.3}>
                <polygon
                  points={`${leftBar + barW},${bs.y} ${rightBar},${as_.y} ${rightBar},${as_.y + as_.h} ${leftBar + barW},${bs.y + bs.h}`}
                  fill={topicColor(hovered)}
                />
              </g>
            );
          })()}

          {/* Bar labels */}
          {[
            { label: "ДО", x: leftBar + barW / 2 },
            { label: "ПОСЛЕ", x: rightBar + barW / 2 },
          ].map(({ label, x }) => (
            <text
              key={label}
              x={x}
              y={H + 20}
              textAnchor="middle"
              fontFamily="JetBrains Mono, monospace"
              fontSize={11}
              fontWeight={500}
              fill={label === "ДО" ? "var(--before)" : "var(--after)"}
              letterSpacing="0.1em"
            >
              {label}
            </text>
          ))}

          {/* Legend */}
          <g transform={`translate(${rightBar + barW + 14}, 0)`}>
            {sorted.map((t, i) => (
              <g key={t.topic_id} transform={`translate(0, ${i * 26})`}>
                <rect
                  width={12}
                  height={12}
                  y={1}
                  fill={topicColor(t.topic_id)}
                  fillOpacity={hovered == null || hovered === t.topic_id ? 0.85 : 0.35}
                  rx={1}
                />
                <text
                  x={16}
                  y={11}
                  fontFamily="var(--font-ui)"
                  fontSize={10}
                  fill={hovered === t.topic_id ? "var(--ink)" : "var(--fog)"}
                  style={{ transition: "fill 100ms" }}
                >
                  {t.name.length > 16 ? t.name.slice(0, 15) + "…" : t.name}
                </text>
              </g>
            ))}
          </g>
        </g>
      </svg>

      <p
        style={{
          fontFamily: "var(--font-ui)",
          fontSize: "13px",
          color: "var(--fog)",
          marginTop: 8,
        }}
      >
        Доля треков, где тема была доминирующей. Наведите для выделения.
      </p>
    </div>
  );
}
