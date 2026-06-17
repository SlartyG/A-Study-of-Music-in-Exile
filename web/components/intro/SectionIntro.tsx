import SectionLabel from "@/components/layout/SectionLabel";

export default function SectionIntro() {
  return (
    <section id="context" className="section">
      <div className="container">
        <SectionLabel section="РАЗДЕЛ 01" title="КОНТЕКСТ" />

        <h2 style={{ marginBottom: 32 }}>Пятая волна</h2>

        <div style={{ maxWidth: 680 }}>
          <p>
            В феврале 2022 года из России начали уезжать музыканты. Не гастрольным
            туром. Насовсем.
          </p>
          <p>
            Некоторые уехали без объяснений. Другие высказались прямо. Несколько
            месяцев спустя большинство из них оказались в реестре иностранных
            агентов Минюста.
          </p>
          <p>
            Угадывать по интервью неудобно. Мы посчитали.
          </p>
        </div>

        {/* Funnel */}
        <FunnelSteps />

        {/* Caveat block */}
        <div
          style={{
            marginTop: 48,
            padding: "20px 24px",
            background: "var(--paper-dark)",
            borderLeft: "3px solid var(--stamp-amber)",
            maxWidth: 520,
          }}
        >
          <p
            style={{
              fontFamily: "var(--font-body)",
              fontStyle: "italic",
              fontSize: "15px",
              color: "var(--ash)",
              marginBottom: 0,
            }}
          >
            Данные: только тексты с Genius, которые сами артисты или фанаты туда
            загрузили. Не все треки представлены, не все с точными датами. Это
            не полная дискография — архив того, что попало в публичный доступ.
          </p>
        </div>
      </div>
    </section>
  );
}

const FUNNEL = [
  {
    count: "50",
    text: "артистов в выборке",
    width: "100%",
  },
  {
    count: "29",
    text: "с данными на Genius (не менее 10 треков в каждом периоде)",
    width: "74%",
  },
  {
    count: "21",
    text: "прошли в итоговый анализ: сбалансированная выборка",
    width: "48%",
  },
];

function FunnelSteps() {
  return (
    <div style={{ marginTop: 48, maxWidth: 560 }}>
      {FUNNEL.map((step, i) => (
        <div key={i} style={{ display: "flex", alignItems: "stretch", marginBottom: 6 }}>
          <div
            style={{
              width: step.width,
              display: "flex",
              alignItems: "center",
              gap: 14,
              border: "1px solid var(--ash)",
              padding: "10px 16px",
            }}
          >
            <span
              style={{
                fontFamily: "var(--font-mono)",
                fontWeight: 700,
                fontSize: "22px",
                color: "var(--ink)",
                flexShrink: 0,
                lineHeight: 1,
              }}
            >
              {step.count}
            </span>
            <span
              style={{
                fontFamily: "var(--font-body)",
                fontSize: "14px",
                color: "var(--ash)",
                lineHeight: 1.4,
              }}
            >
              {step.text}
            </span>
          </div>
        </div>
      ))}

      <p
        style={{
          fontFamily: "var(--font-ui)",
          fontSize: "13px",
          color: "var(--fog)",
          marginTop: 14,
        }}
      >
        N&nbsp;=&nbsp;min(треков «до», треков «после») самых новых по дате выпуска.
        Иначе «до» охватывало бы 15 лет карьеры, а «после» только три.
      </p>
    </div>
  );
}
