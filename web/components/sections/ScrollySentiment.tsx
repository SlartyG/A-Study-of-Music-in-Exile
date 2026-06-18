"use client";
import { useEffect, useRef, useState } from "react";
import type { ArtistMeta, SentimentTrack } from "@/lib/data";
import SectionLabel from "@/components/layout/SectionLabel";
import dynamic from "next/dynamic";
import SummaryTable from "@/components/charts/SummaryTable";
import DeltaDotPlot from "@/components/charts/DeltaDotPlot";
import ArtistPanel from "@/components/artists/ArtistPanel";

const ViolinChart = dynamic(() => import("@/components/charts/ViolinChart"), {
  ssr: false,
  loading: () => (
    <div
      style={{
        height: 360,
        background: "var(--paper-dark)",
        borderRadius: 2,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        fontFamily: "var(--font-mono)",
        fontSize: 12,
        color: "var(--fog)",
      }}
    >
      загрузка…
    </div>
  ),
});

const STEPS = [
  {
    id: "violin",
    title: "Тональность в обоих периодах «в минусе»",
    text: `Тексты и до, и после отъезда слегка «в минусе».

Средний индекс тональности по корпусу: минус несколько тысячных на слово. Не признак депрессии. Рэп, рок и инди тяготеют к напряжению в текстах по умолчанию. Словарь фиксирует «война», «боль», «ненависть» чаще, чем «радость» и «счастье».

После отъезда средняя тональность почти не изменилась.`,
  },
  {
    id: "table",
    title: "В среднем по 21 артисту сдвига нет",
    text: `Статистический тест не находит значимой разницы: p = 0,53 (словарь), p = 0,76 (нейросеть). Cohen's d около нуля.

Это не значит «точно ничего не изменилось». Данных просто не хватает, чтобы утверждать обратное.

Если изменение и есть, оно меньше жанрового шума.`,
  },
  {
    id: "delta",
    title: "Но у отдельных людей разброс",
    text: `Среднее по корпусу ровное. Картина по артистам нет.

У четверых из 21 словарный метод фиксирует значимый сдвиг. У четверых других то же показала нейросеть.

У Бориса Гребенщикова (иноагент) и Максима Покровского (иноагент) тональность сдвинулась к негативу. У Арсения Морозова к позитиву.

Один и тот же переезд у разных людей означал разное.`,
  },
];

function ScrollStep({
  step,
  children,
  onEnter,
  isActive,
}: {
  step: number;
  children: React.ReactNode;
  onEnter: (step: number) => void;
  isActive: boolean;
}) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const obs = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) onEnter(step);
      },
      { threshold: 0.5, rootMargin: "-10% 0px" }
    );
    if (ref.current) obs.observe(ref.current);
    return () => obs.disconnect();
  }, [step, onEnter]);

  return (
    <div
      ref={ref}
      className="scrolly-step"
      style={{
        padding: "80px 0",
        opacity: isActive ? 1 : 0.4,
        transition: "opacity 300ms ease-out",
      }}
    >
      {children}
    </div>
  );
}

export default function ScrollySentiment({
  tracks,
  artists,
}: {
  tracks: SentimentTrack[];
  artists: ArtistMeta[];
}) {
  const [activeStep, setActiveStep] = useState(0);
  const [selectedArtist, setSelectedArtist] = useState<ArtistMeta | null>(null);

  const charts = [
    <ViolinChart key="violin" data={tracks} />,
    <SummaryTable key="table" />,
    <DeltaDotPlot
      key="delta"
      artists={artists}
      onArtistClick={setSelectedArtist}
    />,
  ];

  return (
    <section id="results" className="section" style={{ background: "var(--paper)" }}>
      <div className="container--wide scrolly-grid">
        {/* Left: steps */}
        <div>
          <div style={{ paddingTop: 0 }}>
            <SectionLabel section="РАЗДЕЛ 04" title="ТОНАЛЬНОСТЬ" />
            <h2 style={{ marginBottom: 0 }}>Что говорят числа</h2>
          </div>

          {STEPS.map((step, i) => (
            <ScrollStep
              key={step.id}
              step={i}
              onEnter={setActiveStep}
              isActive={activeStep === i}
            >
              <h3
                style={{
                  fontSize: "22px",
                  fontFamily: "var(--font-heading)",
                  fontStyle: "normal",
                  fontWeight: 600,
                  color: "var(--ink)",
                  marginBottom: 16,
                }}
              >
                {step.title}
              </h3>
              {step.text.split("\n\n").map((para, pi) => (
                <p
                  key={pi}
                  style={{
                    fontFamily: "var(--font-body)",
                    fontSize: "17px",
                    lineHeight: 1.75,
                    color: "var(--ash)",
                    maxWidth: "100%",
                  }}
                >
                  {para}
                </p>
              ))}
            </ScrollStep>
          ))}
        </div>

        {/* Right: sticky chart */}
        <div className="scrolly-charts">
          {charts.map((chart, i) => (
            <div
              key={i}
              className={`scrolly-chart-item ${
                i === 0 ? "scrolly-chart-item--active" : "scrolly-chart-item--stacked"
              }${activeStep !== i ? " scrolly-chart-item--inactive" : ""}`}
              style={{
                opacity: activeStep === i ? 1 : 0,
                filter: activeStep === i ? "blur(0)" : "blur(6px)",
                transition: "opacity 500ms ease-out, filter 500ms ease-out",
                pointerEvents: activeStep === i ? "auto" : "none",
              }}
            >
              {chart}
            </div>
          ))}
        </div>
      </div>

      {selectedArtist && (
        <ArtistPanel artist={selectedArtist} onClose={() => setSelectedArtist(null)} />
      )}
    </section>
  );
}
