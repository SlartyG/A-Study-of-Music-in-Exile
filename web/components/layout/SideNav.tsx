"use client";
import { useEffect, useState } from "react";

const SECTIONS = [
  { id: "hero",        label: "ВВЕДЕНИЕ" },
  { id: "context",     label: "КОНТЕКСТ" },
  { id: "methods",     label: "МЕТОДЫ" },
  { id: "artists",     label: "АРТИСТЫ" },
  { id: "results",     label: "РЕЗУЛЬТАТЫ" },
  { id: "topics",      label: "ТЕМЫ" },
  { id: "timeline",    label: "ХРОНОЛОГИЯ" },
  { id: "conclusions", label: "ВЫВОДЫ" },
  { id: "caveats",     label: "ОГОВОРКИ" },
];

export default function SideNav() {
  const [active, setActive] = useState("hero");

  useEffect(() => {
    const observers: IntersectionObserver[] = [];
    SECTIONS.forEach(({ id }) => {
      const el = document.getElementById(id);
      if (!el) return;
      const obs = new IntersectionObserver(
        ([entry]) => {
          if (entry.isIntersecting) setActive(id);
        },
        { threshold: 0.3 }
      );
      obs.observe(el);
      observers.push(obs);
    });
    return () => observers.forEach((o) => o.disconnect());
  }, []);

  return (
    <nav
      className="side-nav"
      style={{
        position: "fixed",
        left: 0,
        top: "50%",
        transform: "translateY(-50%)",
        width: "148px",
        padding: "0 16px",
        zIndex: 100,
        display: "flex",
        flexDirection: "column",
        gap: 4,
      }}
      aria-label="Навигация по разделам"
    >
      {SECTIONS.map(({ id, label }) => (
        <a
          key={id}
          href={`#${id}`}
          style={{
            fontFamily: "var(--font-mono)",
            fontSize: "10px",
            fontWeight: 500,
            letterSpacing: "0.08em",
            color: active === id ? "var(--stamp-amber)" : "var(--fog)",
            textDecoration: "none",
            padding: "3px 0",
            display: "block",
            transition: "color 200ms ease-out",
          }}
        >
          {label}
        </a>
      ))}
    </nav>
  );
}
