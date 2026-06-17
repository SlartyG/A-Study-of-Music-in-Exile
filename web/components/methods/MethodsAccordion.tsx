"use client";
import { useState } from "react";
import SectionLabel from "@/components/layout/SectionLabel";

type Sign = 1 | -1 | 0;
const WORDS = ["люблю", "жизнь", "ненавижу", "этот", "серый", "дождь", "домой", "всё"];
const INITIAL_SIGNS: Sign[] = [1, 0, -1, 0, 0, 0, 0, 0];
const SIGN_LABELS: Record<Sign, string> = { 1: "+", "-1": "−", 0: "0" } as unknown as Record<Sign, string>;
const SIGN_COLORS: Record<string, string> = {
  "1": "var(--before)",
  "-1": "var(--stamp-red)",
  "0": "var(--fog)",
};
const CYCLE: Sign[] = [0, 1, -1];

function calcIndex(signs: Sign[]): string {
  const pos = signs.filter((s) => s === 1).length;
  const neg = signs.filter((s) => s === -1).length;
  const total = signs.filter((s) => s !== 0).length;
  if (total === 0) return "0,000";
  const v = (pos - neg) / total;
  return (v >= 0 ? "+" : "−") + Math.abs(v).toFixed(3).replace(".", ",");
}

function WordDemo() {
  const [signs, setSigns] = useState<Sign[]>(INITIAL_SIGNS);
  const toggle = (i: number) => {
    const cur = CYCLE.indexOf(signs[i]);
    const next: Sign[] = [...signs];
    next[i] = CYCLE[(cur + 1) % 3];
    setSigns(next);
  };
  const idx = calcIndex(signs);
  const pos = signs.filter((s) => s === 1).length;
  const neg = signs.filter((s) => s === -1).length;
  const total = signs.filter((s) => s !== 0).length;

  return (
    <div style={{ marginTop: 20 }}>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
        {WORDS.map((word, i) => (
          <button
            key={word}
            onClick={() => toggle(i)}
            style={{
              fontFamily: "var(--font-mono)",
              fontSize: "13px",
              padding: "6px 12px",
              border: `1.5px solid ${SIGN_COLORS[String(signs[i])]}`,
              background: "var(--paper)",
              color: SIGN_COLORS[String(signs[i])],
              cursor: "pointer",
              borderRadius: 2,
              transition: "all 150ms ease-out",
            }}
            title="Кликните для смены знака"
          >
            {word}&nbsp;
            <span style={{ fontWeight: 700 }}>
              {signs[i] === 1 ? "+" : signs[i] === -1 ? "−" : "0"}
            </span>
          </button>
        ))}
      </div>
      <div
        style={{
          marginTop: 16,
          fontFamily: "var(--font-mono)",
          fontSize: "13px",
          color: "var(--typewriter)",
          background: "var(--paper-dark)",
          padding: "12px 16px",
          borderRadius: 2,
        }}
      >
        ({pos}&nbsp;−&nbsp;{neg}) / {total || "?"}&nbsp;=&nbsp;
        <strong style={{ fontSize: 15 }}>{idx}</strong>
      </div>
      <p
        style={{
          fontFamily: "var(--font-ui)",
          fontSize: "13px",
          color: "var(--fog)",
          marginTop: 8,
        }}
      >
        Попробуйте изменить знак любого слова. Индекс пересчитается.
      </p>
    </div>
  );
}

function BalanceDemo() {
  const [balanced, setBalanced] = useState(false);
  const before = balanced ? 14 : 199;
  const after = 14;

  return (
    <div style={{ marginTop: 20 }}>
      <div style={{ display: "flex", gap: 8, marginBottom: 20 }}>
        <button
          onClick={() => setBalanced(false)}
          style={btnStyle(!balanced)}
        >
          Без балансировки
        </button>
        <button
          onClick={() => setBalanced(true)}
          style={btnStyle(balanced)}
        >
          С балансировкой
        </button>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
        {[
          { label: "До отъезда", count: before, color: "var(--before)" },
          { label: "После отъезда", count: after, color: "var(--after)" },
        ].map(({ label, count, color }) => (
          <div key={label}>
            <div
              style={{
                fontFamily: "var(--font-mono)",
                fontSize: "11px",
                color: "var(--fog)",
                marginBottom: 4,
              }}
            >
              {label}&nbsp;·&nbsp;{count}&nbsp;треков
            </div>
            <div
              style={{
                height: 14,
                background: color,
                opacity: 0.7,
                width: `${Math.min((count / 200) * 100, 100)}%`,
                transition: "width 500ms ease-out",
                borderRadius: 1,
                minWidth: 4,
              }}
            />
          </div>
        ))}
      </div>

      <p
        style={{
          fontFamily: "var(--font-body)",
          fontStyle: "italic",
          fontSize: "15px",
          color: "var(--ash)",
          marginTop: 16,
          maxWidth: 480,
        }}
      >
        {balanced
          ? "«Как две одинаковые фотоплёнки вместо полного альбома и одной открытки»"
              : "Сравнение всей карьеры с тремя годами эмиграции не отвечает на вопрос про переезд."}
      </p>
    </div>
  );
}

function btnStyle(active: boolean) {
  return {
    fontFamily: "var(--font-ui)" as const,
    fontSize: "13px",
    padding: "6px 14px",
    border: "1px solid var(--ash)",
    background: active ? "var(--stamp-amber)" : "var(--paper)",
    color: active ? "var(--ink)" : "var(--ash)",
    cursor: "pointer" as const,
    borderRadius: 2,
  };
}

const TABS = [
  {
    id: "lexical",
    label: "01 / Словарный термометр",
    content: (
      <>
        <p>
          Компьютер идёт по тексту слово за словом и сверяется со списком:
          это слово обычно звучит позитивно или негативно?
        </p>
        <p>
          «Любовь»: плюс, «война»: минус, «дождь»: ноль.
          Итог: индекс от −1 до +1. У рэпа и рока он почти всегда
          немного ниже нуля. Это жанровая норма, не тревожный сигнал.
        </p>
        <p
          style={{
            fontFamily: "var(--font-body)",
            fontStyle: "italic",
            fontSize: "14px",
            color: "var(--fog)",
          }}
        >
          Слабое место: «Не рад, что ты ушёл» для словаря читается как плюс,
          потому что «рад» в списке позитивных. Отрицание он не видит.
        </p>
        <WordDemo />
      </>
    ),
  },
  {
    id: "lda",
    label: "02 / Поиск тем",
    content: (
      <>
        <p>
          Алгоритм сам находит «кучи» слов, которые часто появляются
          вместе, без заданных нами категорий «протест» или «ностальгия».
        </p>
        <p>
          Представьте архив из тысячи писем без конвертов. В одной куче
          постоянно встречаются «дом», «мама», «снег»; в другой «деньги»,
          «бит», «улица». LDA делает то же статистически.
        </p>
        <LdaCircles />
        <p
          style={{
            fontFamily: "var(--font-body)",
            fontStyle: "italic",
            fontSize: "14px",
            color: "var(--fog)",
            marginTop: 12,
          }}
        >
          Мы не искали «патриотизм» или «протест». Машина нашла
          статистические кластеры. Названия тем мы придумали сами.
        </p>
      </>
    ),
  },
  {
    id: "bert",
    label: "03 / Второй взгляд: нейросеть",
    content: (
      <>
        <p>
          Словарь не понимает контекста. Нейросеть понимает чуть лучше.
          Модель читает не отдельное слово, а фрагмент фразы.
        </p>
        <BertTable />
        <p
          style={{
            fontFamily: "var(--font-body)",
            fontStyle: "italic",
            fontSize: "14px",
            color: "var(--fog)",
            marginTop: 12,
          }}
        >
          Обучали модель на отзывах и постах, а не на песнях. Поэтому
          используем её как «второе мнение» рядом со словарём.
        </p>
      </>
    ),
  },
  {
    id: "balance",
    label: "04 / Как мы сравниваем честно",
    content: (
      <>
        <p>
          У Земфиры (иноагент) на Genius 199 треков до переезда и 14 после.
          Если сравнить всё «до» со всем «после», вы сравниваете 25 лет
          карьеры с двумя годами. Это не ответ на вопрос про эмиграцию.
        </p>
        <p>
          Наше правило: берём N&nbsp;=&nbsp;min(треков до, треков после),
          только самые новые по дате.
        </p>
        <BalanceDemo />
      </>
    ),
  },
];

function LdaCircles() {
  const clusters = [
    { name: "Дом и время", words: ["дом", "любовь", "день", "снег"] },
    { name: "Личное", words: ["хочу", "тобой", "свет", "нужно"] },
    { name: "Деньги", words: ["кэш", "бит", "улица", "кровь"] },
  ];
  return (
    <div style={{ display: "flex", gap: 20, flexWrap: "wrap", marginTop: 20, marginBottom: 4 }}>
      {clusters.map((c) => (
        <div
          key={c.name}
          style={{
            border: "1.5px solid var(--ash)",
            borderRadius: "50%",
            width: 120,
            height: 120,
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            gap: 3,
            padding: 24,
            textAlign: "center",
            overflow: "hidden",
            flexShrink: 0,
          }}
        >
          <div
            style={{
              fontFamily: "var(--font-mono)",
              fontSize: "9px",
              color: "var(--stamp-amber)",
              letterSpacing: "0.04em",
              marginBottom: 3,
              textTransform: "uppercase",
            }}
          >
            {c.name}
          </div>
          {c.words.map((w) => (
            <div
              key={w}
              style={{ fontFamily: "var(--font-mono)", fontSize: "10px", color: "var(--ash)" }}
            >
              {w}
            </div>
          ))}
        </div>
      ))}
    </div>
  );
}

function BertTable() {
  const rows = [
    { label: "ФРАЗА", value: "«Не рад, что ты ушёл»" },
    { label: "СЛОВАРЬ ВИДИТ", value: "«рад» → +1 → ложный плюс" },
    { label: "НЕЙРОСЕТЬ ВИДИТ", value: "«не рад» → скорее негативно" },
  ];
  return (
    <div
      style={{
        marginTop: 20,
        fontFamily: "var(--font-mono)",
        fontSize: "13px",
        border: "1px solid var(--ash)",
        borderRadius: 2,
        overflow: "hidden",
      }}
    >
      {rows.map((r, i) => (
        <div
          key={r.label}
          style={{
            display: "grid",
            gridTemplateColumns: "180px 1fr",
            borderBottom: i < rows.length - 1 ? "1px solid var(--grid)" : "none",
          }}
        >
          <div
            style={{
              padding: "10px 14px",
              color: "var(--fog)",
              borderRight: "1px solid var(--grid)",
              fontSize: "11px",
              letterSpacing: "0.08em",
              textTransform: "uppercase",
            }}
          >
            {r.label}
          </div>
          <div style={{ padding: "10px 14px", color: "var(--typewriter)" }}>{r.value}</div>
        </div>
      ))}
    </div>
  );
}

export default function MethodsAccordion() {
  const [open, setOpen] = useState<string | null>(null);

  return (
    <section id="methods" className="section" style={{ background: "var(--paper)" }}>
      <div className="container">
        <SectionLabel section="РАЗДЕЛ 02" title="МЕТОДОЛОГИЯ" />
        <h2 style={{ marginBottom: 8 }}>Методы</h2>
        <p
          style={{
            fontFamily: "var(--font-body)",
            fontStyle: "italic",
            fontSize: "16px",
            color: "var(--ash)",
            marginBottom: 40,
          }}
        >
          Три инструмента. Читать необязательно: данные работают без этого.
          Но если интересно, как именно мы считали:
        </p>

        <div style={{ display: "flex", flexDirection: "column", gap: 1 }}>
          {TABS.map((tab) => (
            <div
              key={tab.id}
              style={{ borderTop: "1px solid var(--grid)" }}
            >
              <button
                onClick={() => setOpen(open === tab.id ? null : tab.id)}
                style={{
                  width: "100%",
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  padding: "18px 0",
                  background: "none",
                  border: "none",
                  cursor: "pointer",
                  fontFamily: "var(--font-mono)",
                  fontSize: "15px",
                  color: "var(--ink)",
                  textAlign: "left",
                }}
                aria-expanded={open === tab.id}
              >
                <span>{tab.label}</span>
                <span
                  style={{
                    transform: open === tab.id ? "rotate(90deg)" : "none",
                    transition: "transform 300ms ease-out",
                    color: "var(--stamp-amber)",
                    fontSize: 18,
                  }}
                >
                  ›
                </span>
              </button>

              <div
                style={{
                  overflow: "hidden",
                  maxHeight: open === tab.id ? "600px" : "0",
                  transition: "max-height 400ms ease-out",
                }}
              >
                <div
                  style={{
                    paddingBottom: 28,
                    paddingRight: 24,
                    fontFamily: "var(--font-body)",
                    fontSize: "17px",
                    lineHeight: 1.7,
                    color: "var(--ash)",
                  }}
                >
                  {tab.content}
                </div>
              </div>
            </div>
          ))}
          <div style={{ borderTop: "1px solid var(--grid)" }} />
        </div>
      </div>
    </section>
  );
}
