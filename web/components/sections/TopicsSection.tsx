import type { Topic } from "@/lib/data";
import SectionLabel from "@/components/layout/SectionLabel";
import DivergingBar from "@/components/charts/DivergingBar";
import StackedBar from "@/components/charts/StackedBar";

export default function TopicsSection({ topics }: { topics: Topic[] }) {
  return (
    <section id="topics" className="section">
      <div className="container--wide">
        <SectionLabel section="РАЗДЕЛ 05" title="ТЕМАТИКА" />
        <h2 style={{ marginBottom: 16 }}>О чём стали петь иначе</h2>

        <div style={{ maxWidth: 680, marginBottom: 48 }}>
          <p>
            Тональность почти не сдвинулась. Темы изменились.
          </p>
          <p>
            Статистический тест на распределение доминирующих тем между «до»
            и «после» показывает значимое различие: p&nbsp;≈&nbsp;0,008. Это
            устойчивее, чем разница в «настроении».
          </p>
          <p>
            Алгоритм нашёл 10 повторяющихся словесных кластеров. Мы назвали
            каждый по самым характерным словам, насколько это возможно при
            таком жанровом разнообразии.
          </p>
        </div>

        <div className="topics-charts-grid" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 48, alignItems: "start" }}>
          <div>
            <h3
              style={{
                fontSize: "20px",
                fontStyle: "normal",
                fontWeight: 600,
                fontFamily: "var(--font-heading)",
                marginBottom: 20,
              }}
            >
              Что изменилось
            </h3>
            <DivergingBar topics={topics} />
          </div>

          <div>
            <h3
              style={{
                fontSize: "20px",
                fontStyle: "normal",
                fontWeight: 600,
                fontFamily: "var(--font-heading)",
                marginBottom: 20,
              }}
            >
              Структура текстов
            </h3>
            <StackedBar topics={topics} />
          </div>
        </div>

        <div
          style={{
            marginTop: 48,
            padding: "20px 24px",
            background: "var(--paper-dark)",
            borderLeft: "3px solid var(--stamp-amber)",
            maxWidth: 620,
          }}
        >
          <p
            style={{
              fontFamily: "var(--font-body)",
              fontStyle: "italic",
              fontSize: "16px",
              color: "var(--ash)",
              marginBottom: 0,
            }}
          >
            После отъезда в текстах становится меньше тем, связанных со временем
            и деньгами. Растут кластеры с более прямолинейными обращениями и
            личными историями.
          </p>
          <p
            style={{
              fontFamily: "var(--font-body)",
              fontStyle: "italic",
              fontSize: "15px",
              color: "var(--fog)",
              marginTop: 12,
              marginBottom: 0,
            }}
          >
            Интерпретация осторожная: тематический сдвиг устойчивый, но в
            разных жанрах он значит разное.
          </p>
        </div>
      </div>

    </section>
  );
}
