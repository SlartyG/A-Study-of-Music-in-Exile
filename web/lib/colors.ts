export const colors = {
  black: "#0D0D0D",
  paper: "#F0EBE0",
  ink: "#1A1A1A",
  ash: "#3A3A3A",
  fog: "#8A8A8A",
  stampRed: "#C1272D",
  stampAmber: "#D4A017",
  typewriter: "#4A3728",
  before: "#4A7FA5",
  after: "#C1272D",
  grid: "#D8D0C4",
  paperDark: "#E4DDCF",
} as const;

/** 10-step warm monochrome palette for stacked topic bars */
export function topicColor(index: number): string {
  const stops = [
    "#C8B8A0", "#B8A488", "#A89070", "#987C58", "#886848",
    "#785438", "#684028", "#582C1C", "#480C0C", "#3A2010",
  ];
  return stops[Math.min(index, stops.length - 1)];
}
