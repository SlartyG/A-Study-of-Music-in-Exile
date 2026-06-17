interface Props {
  section: string;
  title: string;
  dark?: boolean;
}

export default function SectionLabel({ section, title, dark }: Props) {
  return (
    <div
      className="section-label"
      style={{ color: dark ? "rgba(245,245,245,0.5)" : undefined }}
    >
      {section}&nbsp;/&nbsp;{title}
    </div>
  );
}
