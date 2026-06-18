"use client";
import { useEffect, useRef } from "react";
import type { SentimentTrack } from "@/lib/data";
import { colors } from "@/lib/colors";

interface Props {
  data: SentimentTrack[];
  width?: number;
  height?: number;
}

function kde(values: number[], points: number[], bandwidth: number): [number, number][] {
  const kernel = (v: number) => {
    const u = v / bandwidth;
    return Math.abs(u) <= 1 ? (0.75 * (1 - u * u)) / bandwidth : 0;
  };
  return points.map((x) => [
    x,
    values.reduce((sum, v) => sum + kernel(x - v), 0) / values.length,
  ]);
}

function linspace(start: number, stop: number, n: number): number[] {
  const step = (stop - start) / (n - 1);
  return Array.from({ length: n }, (_, i) => start + i * step);
}

function median(arr: number[]): number {
  const s = [...arr].sort((a, b) => a - b);
  const mid = Math.floor(s.length / 2);
  return s.length % 2 ? s[mid] : (s[mid - 1] + s[mid]) / 2;
}

export default function ViolinChart({ data, width = 560, height = 360 }: Props) {
  const svgRef = useRef<SVGSVGElement>(null);

  useEffect(() => {
    const svg = svgRef.current;
    if (!svg || data.length === 0) return;

    const margin = { top: 20, right: 20, bottom: 48, left: 56 };
    const W = width - margin.left - margin.right;
    const H = height - margin.top - margin.bottom;

    // Clear previous
    while (svg.firstChild) svg.removeChild(svg.firstChild);

    const ns = "http://www.w3.org/2000/svg";

    const g = document.createElementNS(ns, "g");
    g.setAttribute("transform", `translate(${margin.left},${margin.top})`);
    svg.appendChild(g);

    // Data per group
    const groups: Array<{ key: "before" | "after"; label: string; color: string }> = [
      { key: "before", label: "ДО", color: colors.before },
      { key: "after", label: "ПОСЛЕ", color: colors.after },
    ];

    const allValues = data.map((d) => d.sentiment_ratio);
    const yMin = -0.12;
    const yMax = 0.10;

    // Scales
    const yScale = (v: number) => H - ((v - yMin) / (yMax - yMin)) * H;
    const groupWidth = W / 2;
    const xOffset = (i: number) => i * groupWidth + groupWidth / 2;

    // Grid lines
    const gridVals = [-0.10, -0.06, -0.02, 0, 0.02, 0.06];
    gridVals.forEach((v) => {
      const y = yScale(v);
      const line = document.createElementNS(ns, "line");
      line.setAttribute("x1", "0");
      line.setAttribute("x2", String(W));
      line.setAttribute("y1", String(y));
      line.setAttribute("y2", String(y));
      line.setAttribute("stroke", v === 0 ? colors.ash : colors.grid);
      line.setAttribute("stroke-width", v === 0 ? "1.5" : "1");
      if (v === 0) line.setAttribute("stroke-dasharray", "4,3");
      g.appendChild(line);

      const label = document.createElementNS(ns, "text");
      label.setAttribute("x", "-8");
      label.setAttribute("y", String(y + 4));
      label.setAttribute("text-anchor", "end");
      label.setAttribute("font-family", "JetBrains Mono, monospace");
      label.setAttribute("font-size", "10");
      label.setAttribute("fill", colors.fog);
      label.textContent = v.toFixed(2).replace(".", ",");
      g.appendChild(label);
    });

    // Zero line label
    const zeroLabel = document.createElementNS(ns, "text");
    zeroLabel.setAttribute("x", "-8");
    zeroLabel.setAttribute("y", String(yScale(0) + 4));
    zeroLabel.setAttribute("text-anchor", "end");
    zeroLabel.setAttribute("font-family", "JetBrains Mono, monospace");
    zeroLabel.setAttribute("font-size", "10");
    zeroLabel.setAttribute("fill", colors.ash);
    zeroLabel.setAttribute("font-weight", "500");
    zeroLabel.textContent = "0";

    // KDE points
    const kdePoints = linspace(yMin, yMax, 200);
    const bandwidth = 0.006;

    groups.forEach(({ key, label, color }, i) => {
      const values = data.filter((d) => d.period === key).map((d) => d.sentiment_ratio);
      if (values.length === 0) return;

      const density = kde(values, kdePoints, bandwidth);
      const maxD = Math.max(...density.map((d) => d[1]));
      const maxHalfWidth = groupWidth * 0.42;
      const densityToX = (d: number) => (d / maxD) * maxHalfWidth;

      const cx = xOffset(i);

      // Build violin path
      const rightPath = density.map(([y, d]) => `${cx + densityToX(d)},${yScale(y)}`);
      const leftPath = [...density]
        .reverse()
        .map(([y, d]) => `${cx - densityToX(d)},${yScale(y)}`);

      const path = document.createElementNS(ns, "path");
      path.setAttribute(
        "d",
        `M${rightPath[0]} ${rightPath.slice(1).map((p) => `L${p}`).join(" ")} ${leftPath.map((p) => `L${p}`).join(" ")} Z`
      );
      path.setAttribute("fill", color);
      path.setAttribute("fill-opacity", "0.45");
      path.setAttribute("stroke", color);
      path.setAttribute("stroke-width", "1.5");
      g.appendChild(path);

      // Median line
      const med = median(values);
      const iqr25 = values.sort((a, b) => a - b)[Math.floor(values.length * 0.25)];
      const iqr75 = values.sort((a, b) => a - b)[Math.floor(values.length * 0.75)];

      // IQR bar
      const iqrRect = document.createElementNS(ns, "rect");
      iqrRect.setAttribute("x", String(cx - 3));
      iqrRect.setAttribute("y", String(yScale(iqr75)));
      iqrRect.setAttribute("width", "6");
      iqrRect.setAttribute("height", String(Math.abs(yScale(iqr25) - yScale(iqr75))));
      iqrRect.setAttribute("fill", color);
      iqrRect.setAttribute("fill-opacity", "0.7");
      g.appendChild(iqrRect);

      // Median tick
      const medLine = document.createElementNS(ns, "line");
      medLine.setAttribute("x1", String(cx - maxHalfWidth * 0.5));
      medLine.setAttribute("x2", String(cx + maxHalfWidth * 0.5));
      medLine.setAttribute("y1", String(yScale(med)));
      medLine.setAttribute("y2", String(yScale(med)));
      medLine.setAttribute("stroke", colors.ink);
      medLine.setAttribute("stroke-width", "2");
      g.appendChild(medLine);

      // Group label
      const txt = document.createElementNS(ns, "text");
      txt.setAttribute("x", String(cx));
      txt.setAttribute("y", String(H + 28));
      txt.setAttribute("text-anchor", "middle");
      txt.setAttribute("font-family", "JetBrains Mono, monospace");
      txt.setAttribute("font-size", "12");
      txt.setAttribute("font-weight", "500");
      txt.setAttribute("fill", color);
      txt.setAttribute("letter-spacing", "0.1em");
      txt.textContent = label;
      g.appendChild(txt);

      // Median annotation
      const annot = document.createElementNS(ns, "text");
      annot.setAttribute("x", String(cx + maxHalfWidth + 4));
      annot.setAttribute("y", String(yScale(med) + 4));
      annot.setAttribute("font-family", "JetBrains Mono, monospace");
      annot.setAttribute("font-size", "9");
      annot.setAttribute("fill", colors.fog);
      annot.textContent = `мед ${med.toFixed(3).replace(".", ",")}`;
      g.appendChild(annot);
    });
  }, [data, width, height]);

  return (
    <div className="chart-wrap">
      <svg
        ref={svgRef}
        viewBox={`0 0 ${width} ${height}`}
        width="100%"
        preserveAspectRatio="xMidYMid meet"
        style={{ maxWidth: width, background: colors.paper, display: "block" }}
        aria-label="Violin-диаграмма распределения тональности до и после"
        role="img"
      />
      <p
        style={{
          fontFamily: "var(--font-ui)",
          fontSize: "13px",
          color: "var(--fog)",
          marginTop: 8,
        }}
      >
        Каждая фигура — распределение сотен треков. Горизонтальная черта — медиана.
      </p>
    </div>
  );
}
