import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Музыка после отъезда — Веселов Александр",
  description:
    "Как изменились тексты 21 российского музыканта после эмиграции 2022 года. Количественное исследование с помощью NLP.",
  metadataBase: new URL("https://example.com"),
  openGraph: {
    title: "Музыка после отъезда",
    description:
      "21 артист, 1158 треков, три метода анализа. Изменились ли тексты после переезда?",
    type: "article",
    locale: "ru_RU",
  },
  twitter: {
    card: "summary",
    title: "Музыка после отъезда",
    description: "21 артист, 1158 треков, три метода NLP-анализа.",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="ru">
      <head>
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <meta name="theme-color" content="#0D0D0D" />
      </head>
      <body>
        <a href="#main-content" className="skip-link">
          Перейти к содержимому
        </a>
        {children}
      </body>
    </html>
  );
}
