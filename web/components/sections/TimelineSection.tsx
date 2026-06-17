"use client";
import { useEffect, useRef } from "react";
import type { TimelinePoint } from "@/lib/data";
import { colors } from "@/lib/colors";
import SectionLabel from "@/components/layout/SectionLabel";

interface Props {
  timeline: TimelinePoint[];
}

export default function TimelineSection({ timeline }: Props) {
  const svgRef = useRef<SVGSVGElement>(null);

  useEffect(() => {
    const svg = svgRef.current;
    // Only show years with reasonable coverage (skip sparse early catalog years)
    const data = timeline.filter((d) => d.year >= 2016 && d.n >= 5);
    if (!svg || data.length === 0) return;

    const W = 560;
    const H = 260;
    const margin = { top: 24, right: 24, bottom: 44, left: 60 };
    const plotW = W - margin.left - margin.right;
    const plotH = H - margin.top - margin.bottom;

    while (svg.firstChild) svg.removeChild(svg.firstChild);
    const ns = "http://www.w3.org/2000/svg";

    const g = document.createElementNS(ns, "g");
    g.setAttribute("transform", `translate(${margin.left},${margin.top})`);
    svg.appendChild(g);

    const years = data.map((d) => d.year);
    const minYear = Math.min(...years);
    const maxYear = Math.max(...years);
    const allMeans = data.map((d) => d.mean_lex);
    const yMin = Math.min(...allMeans) - 0.004;
    const yMax = Math.max(...allMeans) + 0.004;

    const xScale = (y: number) => ((y - minYear) / (maxYear - minYear)) * plotW;
    const yScale = (v: number) => plotH - ((v - yMin) / (yMax - yMin)) * plotH;

    // Horizontal grid lines
    const yTicks = [-0.012, -0.008, -0.004, 0, 0.004];
    yTicks.forEach((v) => {
      if (v < yMin || v > yMax) return;
      const y = yScale(v);
      const line = document.createElementNS(ns, "line");
      line.setAttribute("x1", "0");
      line.setAttribute("x2", String(plotW));
      line.setAttribute("y1", String(y));
      line.setAttribute("y2", String(y));
      line.setAttribute("stroke", v === 0 ? colors.ash : colors.grid);
      line.setAttribute("stroke-width", v === 0 ? "1.5" : "0.8");
      if (v === 0) line.setAttribute("stroke-dasharray", "4,3");
      g.appendChild(line);

      const label = document.createElementNS(ns, "text");
      label.setAttribute("x", "-8");
      label.setAttribute("y", String(y + 4));
      label.setAttribute("text-anchor", "end");
      label.setAttribute("font-family", "JetBrains Mono, monospace");
      label.setAttribute("font-size", "9");
      label.setAttribute("fill", colors.fog);
      label.textContent = v.toFixed(3).replace(".", ",");
      g.appendChild(label);
    });

    // 2022 vertical divider
    const x2022 = xScale(2022);
    const vLine = document.createElementNS(ns, "line");
    vLine.setAttribute("x1", String(x2022));
    vLine.setAttribute("x2", String(x2022));
    vLine.setAttribute("y1", "0");
    vLine.setAttribute("y2", String(plotH));
    vLine.setAttribute("stroke", colors.stampRed);
    vLine.setAttribute("stroke-width", "1.5");
    vLine.setAttribute("stroke-dasharray", "5,3");
    g.appendChild(vLine);

    const divLabel = document.createElementNS(ns, "text");
    divLabel.setAttribute("x", String(x2022 + 4));
    divLabel.setAttribute("y", "12");
    divLabel.setAttribute("font-family", "JetBrains Mono, monospace");
    divLabel.setAttribute("font-size", "9");
    divLabel.setAttribute("fill", colors.stampRed);
    divLabel.setAttribute("letter-spacing", "0.08em");
    divLabel.textContent = "2022 →";
    g.appendChild(divLabel);

    // Area shading for each period
    const before = data.filter((d) => d.period_cal === "before");
    const after = data.filter((d) => d.period_cal === "after");

    function buildArea(pts: TimelinePoint[], color: string) {
      if (pts.length < 2) return;
      const topPts = pts.map((d) => `${xScale(d.year)},${yScale(d.mean_lex + d.sem_lex)}`).join(" L ");
      const bottomPts = [...pts]
        .reverse()
        .map((d) => `${xScale(d.year)},${yScale(d.mean_lex - d.sem_lex)}`)
        .join(" L ");
      const area = document.createElementNS(ns, "path");
      area.setAttribute("d", `M${topPts} L${bottomPts} Z`);
      area.setAttribute("fill", color);
      area.setAttribute("fill-opacity", "0.12");
      g.appendChild(area);
    }

    buildArea(before, colors.before);
    buildArea(after, colors.after);

    // Bridge SEM band + mean line between last "before" and first "after" (e.g. 2021→2022).
    // Uses "before" color; the 2022 dot itself stays "after" colored.
    const lastBefore = before[before.length - 1];
    const firstAfter = after[0];
    if (lastBefore && firstAfter) {
      const x1 = xScale(lastBefore.year);
      const x2 = xScale(firstAfter.year);
      const yTop1 = yScale(lastBefore.mean_lex + lastBefore.sem_lex);
      const yTop2 = yScale(firstAfter.mean_lex + firstAfter.sem_lex);
      const yBot1 = yScale(lastBefore.mean_lex - lastBefore.sem_lex);
      const yBot2 = yScale(firstAfter.mean_lex - firstAfter.sem_lex);

      const bridgeArea = document.createElementNS(ns, "path");
      bridgeArea.setAttribute(
        "d",
        `M${x1},${yTop1} L${x2},${yTop2} L${x2},${yBot2} L${x1},${yBot1} Z`
      );
      bridgeArea.setAttribute("fill", colors.before);
      bridgeArea.setAttribute("fill-opacity", "0.12");
      g.appendChild(bridgeArea);

      const bridge = document.createElementNS(ns, "line");
      bridge.setAttribute("x1", String(x1));
      bridge.setAttribute("y1", String(yScale(lastBefore.mean_lex)));
      bridge.setAttribute("x2", String(x2));
      bridge.setAttribute("y2", String(yScale(firstAfter.mean_lex)));
      bridge.setAttribute("stroke", colors.before);
      bridge.setAttribute("stroke-width", "2");
      bridge.setAttribute("stroke-linejoin", "round");
      g.appendChild(bridge);
    }

    // Line for each period
    function buildLine(pts: TimelinePoint[], color: string) {
      if (pts.length < 1) return;
      const d =
        `M${xScale(pts[0].year)},${yScale(pts[0].mean_lex)} ` +
        pts
          .slice(1)
          .map((p) => `L${xScale(p.year)},${yScale(p.mean_lex)}`)
          .join(" ");
      const path = document.createElementNS(ns, "path");
      path.setAttribute("d", d);
      path.setAttribute("fill", "none");
      path.setAttribute("stroke", color);
      path.setAttribute("stroke-width", "2");
      path.setAttribute("stroke-linejoin", "round");
      g.appendChild(path);
    }

    buildLine(before, colors.before);
    buildLine(after, colors.after);

    // Dots
    data.forEach((d) => {
      const circle = document.createElementNS(ns, "circle");
      circle.setAttribute("cx", String(xScale(d.year)));
      circle.setAttribute("cy", String(yScale(d.mean_lex)));
      circle.setAttribute("r", "3");
      circle.setAttribute("fill", d.period_cal === "before" ? colors.before : colors.after);
      circle.setAttribute("fill-opacity", "0.85");
      g.appendChild(circle);
    });

    // X axis labels
    years.forEach((y) => {
      const text = document.createElementNS(ns, "text");
      text.setAttribute("x", String(xScale(y)));
      text.setAttribute("y", String(plotH + 18));
      text.setAttribute("text-anchor", "middle");
      text.setAttribute("font-family", "JetBrains Mono, monospace");
      text.setAttribute("font-size", "9");
      text.setAttribute("fill", y >= 2022 ? colors.after : colors.before);
      text.textContent = String(y);
      g.appendChild(text);
    });
  }, [timeline]);

  return (
    <section id="timeline" className="section section--muted">
      <div className="container">
        <SectionLabel section="РАЗДЕЛ 06" title="ХРОНОЛОГИЯ" />
        <h2 style={{ marginBottom: 16 }}>Тональность по годам</h2>

        <p style={{ marginBottom: 32, color: "var(--ash)" }}>
          График использует все треки корпуса, не только сбалансированные,
          чтобы показать тренд во времени. Год по дате выпуска,
          а не по дате переезда.
        </p>

        <svg
          ref={svgRef}
          viewBox="0 0 560 260"
          width="100%"
          style={{ maxWidth: 560, background: colors.paper, display: "block" }}
          aria-label="Средняя лексическая тональность по годам"
          role="img"
        />

        <div
          style={{
            marginTop: 12,
            display: "flex",
            gap: 24,
            fontFamily: "var(--font-ui)",
            fontSize: "12px",
            color: colors.fog,
          }}
        >
          <span style={{ color: colors.before }}>— ДО 2022</span>
          <span style={{ color: colors.after }}>— ПОСЛЕ 2022</span>
          <span>Полоска = ±1 SEM</span>
        </div>

        <p
          style={{
            marginTop: 16,
            fontFamily: "var(--font-body)",
            fontStyle: "italic",
            fontSize: "14px",
            color: colors.fog,
          }}
        >
          Календарное деление (до/с 2022) используется только для визуализации тренда.
          Статистические тесты использовали индивидуальные даты релокации каждого артиста.
        </p>
      </div>
    </section>
  );
}
