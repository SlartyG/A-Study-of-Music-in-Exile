import { colors } from "@/lib/colors";

const ROWS = [
  {
    method: "Словарный список",
    before: "−0,0071",
    after: "−0,0053",
    d: "+0,047",
    p: "0,532 n.s.",
    significant: false,
  },
  {
    method: "Нейросеть ruBERT",
    before: "−0,1547",
    after: "−0,1510",
    d: "+0,010",
    p: "0,757 n.s.",
    significant: false,
  },
];

export default function SummaryTable() {
  return (
    <div>
      {/* Document header */}
      <div
        style={{
          fontFamily: "var(--font-mono)",
          fontSize: "10px",
          letterSpacing: "0.12em",
          color: colors.fog,
          textTransform: "uppercase",
          marginBottom: 10,
        }}
      >
        ЗАКЛЮЧЕНИЕ ПО ДЕЛУ / ТОНАЛЬНОСТЬ
      </div>

      <div
        style={{
          border: `1px solid ${colors.ash}`,
          borderRadius: 2,
          overflow: "hidden",
          fontFamily: "var(--font-mono)",
          fontSize: "13px",
        }}
      >
        {/* Header row */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "2fr 1fr 1fr 1fr 1.2fr",
            background: colors.paperDark,
            borderBottom: `1px solid ${colors.grid}`,
          }}
        >
          {["МЕТОД", "ДО", "ПОСЛЕ", "D", "P-VALUE"].map((h) => (
            <div
              key={h}
              style={{
                padding: "8px 12px",
                fontSize: "10px",
                letterSpacing: "0.1em",
                color: colors.fog,
                fontWeight: 500,
              }}
            >
              {h}
            </div>
          ))}
        </div>

        {/* Data rows */}
        {ROWS.map((row, i) => (
          <div
            key={i}
            style={{
              display: "grid",
              gridTemplateColumns: "2fr 1fr 1fr 1fr 1.2fr",
              borderBottom: i < ROWS.length - 1 ? `1px solid ${colors.grid}` : "none",
            }}
          >
            <div style={{ padding: "10px 12px", color: colors.typewriter, fontWeight: 500 }}>
              {row.method}
            </div>
            <div style={{ padding: "10px 12px", color: colors.typewriter }}>{row.before}</div>
            <div style={{ padding: "10px 12px", color: colors.typewriter }}>{row.after}</div>
            <div style={{ padding: "10px 12px", color: colors.typewriter }}>{row.d}</div>
            <div
              style={{
                padding: "10px 12px",
                color: row.significant ? colors.stampAmber : colors.fog,
                fontWeight: row.significant ? 600 : 400,
              }}
            >
              {row.p}
            </div>
          </div>
        ))}
      </div>

      <div
        style={{
          marginTop: 10,
          fontFamily: "var(--font-ui)",
          fontSize: "13px",
          color: colors.fog,
          lineHeight: 1.5,
        }}
      >
        n.s. — разница не достигает статистической значимости (p &gt; 0,05)
        <br />
        d — размер эффекта; d &lt; 0,2 считается малым
      </div>
    </div>
  );
}
