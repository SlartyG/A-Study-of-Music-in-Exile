"use client";
import { useEffect, useRef, useState } from "react";
import type { CorpusSummary } from "@/lib/data";

function useTypewriter(text: string, speed = 45) {
  const [displayed, setDisplayed] = useState("");
  const [done, setDone] = useState(false);
  useEffect(() => {
    let i = 0;
    const id = setInterval(() => {
      i++;
      setDisplayed(text.slice(0, i));
      if (i >= text.length) {
        clearInterval(id);
        setDone(true);
      }
    }, speed);
    return () => clearInterval(id);
  }, [text, speed]);
  return { displayed, done };
}

function CountUp({ target, duration = 1200 }: { target: number; duration?: number }) {
  const [value, setValue] = useState(0);
  const ref = useRef<HTMLSpanElement>(null);
  const started = useRef(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting && !started.current) {
          started.current = true;
          const start = performance.now();
          const tick = (now: number) => {
            const p = Math.min((now - start) / duration, 1);
            const eased = 1 - Math.pow(1 - p, 3);
            setValue(Math.round(target * eased));
            if (p < 1) requestAnimationFrame(tick);
          };
          requestAnimationFrame(tick);
        }
      },
      { threshold: 0.5 }
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, [target, duration]);

  return <span ref={ref}>{value.toLocaleString("ru-RU")}</span>;
}

export default function Hero({ corpus }: { corpus: CorpusSummary }) {
  const { displayed, done } = useTypewriter("Музыка после отъезда");

  return (
    <section
      id="hero"
      className="noisy noisy--dark"
      style={{
        minHeight: "100vh",
        background: "var(--black)",
        display: "flex",
        flexDirection: "column",
        justifyContent: "center",
        alignItems: "flex-start",
        padding: "80px 48px",
        position: "relative",
        overflow: "hidden",
      }}
    >
      {/* Scanner lines */}
      <div
        aria-hidden
        style={{
          position: "absolute",
          inset: 0,
          backgroundImage:
            "repeating-linear-gradient(0deg, transparent, transparent 3px, rgba(255,255,255,0.015) 3px, rgba(255,255,255,0.015) 4px)",
          pointerEvents: "none",
          zIndex: 0,
        }}
      />

      <div style={{ position: "relative", zIndex: 2, maxWidth: 760 }}>
        {/* Archive label */}
        <div
          style={{
            fontFamily: "var(--font-mono)",
            fontSize: "11px",
            letterSpacing: "0.15em",
            color: "rgba(245,245,245,0.4)",
            marginBottom: 32,
            textTransform: "uppercase",
          }}
        >
          ИССЛЕДОВАНИЕ / ТЕКСТОВЫЙ АНАЛИЗ / 2026
        </div>

        {/* Main title */}
        <h1
          style={{
            fontFamily: "var(--font-heading)",
            fontSize: "clamp(48px, 8vw, 88px)",
            fontWeight: 700,
            letterSpacing: "-0.02em",
            color: "#F5F5F5",
            lineHeight: 1.05,
            marginBottom: 32,
            minHeight: "1.1em",
          }}
        >
          {displayed}
          <span
            style={{
              display: "inline-block",
              width: 3,
              height: "0.85em",
              background: "var(--stamp-amber)",
              marginLeft: 4,
              verticalAlign: "text-bottom",
              animation: done ? "blink 1s step-end 3 forwards" : "none",
              opacity: done ? undefined : 1,
            }}
            aria-hidden
          />
        </h1>

        {/* Subtitle */}
        <p
          style={{
            fontFamily: "var(--font-body)",
            fontStyle: "italic",
            fontSize: "22px",
            color: "rgba(245,245,245,0.85)",
            maxWidth: 680,
            lineHeight: 1.6,
            marginBottom: 56,
          }}
        >
          {corpus.artists} российских музыкантов уехали в 2022 году.
          Мы посмотрели, что изменилось в их текстах.
        </p>

        {/* Stats row */}
        <div
          style={{
            display: "flex",
            gap: "clamp(24px, 5vw, 64px)",
            flexWrap: "wrap",
          }}
          aria-label="Параметры исследования"
        >
          {[
            { value: corpus.artists, label: "АРТИСТ" },
            { value: corpus.tracks, label: "ТРЕКОВ" },
            { label: corpus.period, isText: true },
          ].map((stat, i) =>
            "isText" in stat ? (
              <div key={i}>
                <div
                  style={{
                    fontFamily: "var(--font-mono)",
                    fontSize: "38px",
                    fontWeight: 700,
                    color: "#F5F5F5",
                    lineHeight: 1,
                  }}
                >
                  {stat.label}
                </div>
                <div
                  style={{
                    fontFamily: "var(--font-mono)",
                    fontSize: "11px",
                    letterSpacing: "0.12em",
                    color: "rgba(245,245,245,0.45)",
                    marginTop: 6,
                    textTransform: "uppercase",
                  }}
                >
                  ПЕРИОД
                </div>
              </div>
            ) : (
              <div key={i}>
                <div
                  style={{
                    fontFamily: "var(--font-mono)",
                    fontSize: "38px",
                    fontWeight: 700,
                    color: "#F5F5F5",
                    lineHeight: 1,
                  }}
                >
                  <CountUp target={stat.value as number} />
                </div>
                <div
                  style={{
                    fontFamily: "var(--font-mono)",
                    fontSize: "11px",
                    letterSpacing: "0.12em",
                    color: "rgba(245,245,245,0.45)",
                    marginTop: 6,
                    textTransform: "uppercase",
                  }}
                >
                  {stat.label}
                </div>
              </div>
            )
          )}
        </div>
      </div>

      {/* Scroll cue */}
      <a
        href="#context"
        style={{
          position: "absolute",
          bottom: 48,
          left: "50%",
          transform: "translateX(-50%)",
          color: "var(--stamp-amber)",
          fontSize: 28,
          textDecoration: "none",
          animation: "float 2s ease-in-out infinite",
          zIndex: 2,
        }}
        aria-label="Прокрутить вниз"
      >
        ↓
      </a>

      <style>{`
        @keyframes blink {
          0%, 100% { opacity: 1; }
          50% { opacity: 0; }
        }
        @keyframes float {
          0%, 100% { transform: translateX(-50%) translateY(0); }
          50% { transform: translateX(-50%) translateY(8px); }
        }
        @media (max-width: 640px) {
          section#hero { padding: 60px 20px; }
        }
        @media (prefers-reduced-motion: reduce) {
          @keyframes float { from {} to {} }
          @keyframes blink { from {} to {} }
        }
      `}</style>
    </section>
  );
}
