"use client";
import { useEffect, useRef, useState } from "react";
import SectionLabel from "@/components/layout/SectionLabel";

const THESES = [
  {
    num: "01",
    text: `Тексты российских музыкантов и до, и после 2022 года в среднем «в минусе» по тональности. Это жанровая норма, не следствие эмиграции.`,
  },
  {
    num: "02",
    text: `На сбалансированной выборке общего сдвига тональности нет. Словарный метод: p\u202f=\u202f0,53; нейросеть: p\u202f=\u202f0,76. Размер эффекта около нуля.`,
  },
  {
    num: "03",
    text: `У части артистов личный сдвиг есть, причём в разные стороны. Четыре из 21 показали значимое изменение по словарю, ещё четыре по нейросети. У одних к негативу, у других к позитиву.`,
  },
  {
    num: "04",
    text: `Тематический состав текстов меняется значимее, чем «настроение». χ²-тест: p\u202f≈\u202f0,008. После отъезда одни словесные кластеры редеют, другие растут.`,
  },
  {
    num: "05",
    text: `Разделение на «с особым статусом» и «без» не даёт устойчивого группового различия в тональности (p\u202f>\u202f0,7 в обеих группах). Траектории внутри групп расходятся.`,
  },
  {
    num: "06",
    text: `Переезд не сделал тексты единообразно мрачнее. По этим данным он связан скорее со сменой того, о чём пишут, чем с универсальным потемнением.`,
  },
];

function Thesis({ num, text, delay }: { num: string; text: string; delay: number }) {
  const [visible, setVisible] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const obs = new IntersectionObserver(
      ([e]) => {
        if (e.isIntersecting) {
          setTimeout(() => setVisible(true), delay);
          obs.disconnect();
        }
      },
      { threshold: 0.3 }
    );
    if (ref.current) obs.observe(ref.current);
    return () => obs.disconnect();
  }, [delay]);

  return (
    <div
      ref={ref}
      style={{
        display: "flex",
        gap: 24,
        alignItems: "flex-start",
        paddingBottom: 32,
        borderBottom: "1px solid rgba(245,245,245,0.08)",
        opacity: visible ? 1 : 0,
        transform: visible ? "none" : "translateY(20px)",
        transition: "opacity 400ms ease-out, transform 400ms ease-out",
      }}
    >
      <div
        style={{
          fontFamily: "var(--font-mono)",
          fontSize: "28px",
          fontWeight: 700,
          color: "var(--stamp-amber)",
          lineHeight: 1,
          flexShrink: 0,
          paddingTop: 4,
        }}
      >
        {num}.
      </div>
      <p
        style={{
          fontFamily: "var(--font-body)",
          fontSize: "18px",
          lineHeight: 1.7,
          color: "rgba(245,245,245,0.88)",
          marginBottom: 0,
          maxWidth: "none",
        }}
      >
        {text}
      </p>
    </div>
  );
}

export default function Conclusions() {
  return (
    <>
      <section
        id="conclusions"
        className="section section--dark noisy noisy--dark"
      >
        <div className="container">
          <SectionLabel section="РАЗДЕЛ 07" title="ВЫВОДЫ" dark />
          <h2 style={{ color: "#F5F5F5", marginBottom: 48 }}>Итого</h2>

          <div style={{ display: "flex", flexDirection: "column", gap: 0 }}>
            {THESES.map((t, i) => (
              <Thesis key={t.num} num={t.num} text={t.text} delay={i * 100} />
            ))}
          </div>
        </div>
      </section>

      <section id="caveats" className="section section--muted">
        <div className="container">
          <h3
            style={{
              fontFamily: "var(--font-heading)",
              fontSize: "28px",
              fontStyle: "italic",
              fontWeight: 600,
              marginBottom: 24,
              color: "var(--ash)",
            }}
          >
            Ограничения исследования
          </h3>

          <p
            style={{
              fontFamily: "var(--font-body)",
              fontSize: "15px",
              color: "var(--ash)",
              lineHeight: 1.75,
            }}
          >
            Данные: только публичные тексты с Genius. Часть треков не загружена
            или загружена без дат. Это не полные дискографии.
          </p>
          <p
            style={{
              fontFamily: "var(--font-body)",
              fontSize: "15px",
              color: "var(--ash)",
              lineHeight: 1.75,
            }}
          >
            Метод 1 не обрабатывает мат, жаргон и отрицания корректно.
            Метод 3 обучен на отзывах, не на художественных текстах.
            Оба приближения.
          </p>
          <p
            style={{
              fontFamily: "var(--font-body)",
              fontSize: "15px",
              color: "var(--ash)",
              lineHeight: 1.75,
            }}
          >
            Размер корпуса небольшой: 21 артист, ~1&nbsp;600 треков.
            Статистические выводы работают для этой выборки, а не для «всей
            российской музыки».
          </p>
          <p
            style={{
              fontFamily: "var(--font-body)",
              fontSize: "15px",
              color: "var(--ash)",
              lineHeight: 1.75,
            }}
          >
            Имена артистов с официальным статусом «иностранный агент»
            употребляются в исследовательских целях с указанием их правового
            статуса в соответствии с законодательством Российской Федерации.
            Работа носит академический и информационный характер.
          </p>

          <hr className="divider" />

          <div
            style={{
              fontFamily: "var(--font-ui)",
              fontSize: "14px",
              color: "var(--fog)",
              lineHeight: 2,
            }}
          >
            <p>
              Методология подробно:{" "}
              <span style={{ fontFamily: "var(--font-mono)", fontSize: 12 }}>
                METHODOLOGY_LEXICAL.md&nbsp;/&nbsp;METHODOLOGY_TOPIC_MODELING.md&nbsp;/&nbsp;METHODOLOGY_TRANSFORMERS.md
              </span>
            </p>
            <p>
              Данные и код:{" "}
              <a
                href="https://github.com/SlartyG/A-Study-of-Music-in-Exile"
                target="_blank"
                rel="noopener noreferrer"
                style={{ color: "var(--stamp-amber)" }}
              >
                github.com/SlartyG/A-Study-of-Music-in-Exile
              </a>
            </p>
            <p style={{ marginTop: 16, color: "var(--ash)", fontSize: "13px" }}>
              Автор: Веселов Александр
            </p>
          </div>
        </div>
      </section>
    </>
  );
}
