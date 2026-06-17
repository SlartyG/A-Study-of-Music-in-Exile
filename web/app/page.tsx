import { loadAllData } from "@/lib/data";
import LegalBanner from "@/components/layout/LegalBanner";
import SideNav from "@/components/layout/SideNav";
import Hero from "@/components/hero/Hero";
import SectionIntro from "@/components/intro/SectionIntro";
import MethodsAccordion from "@/components/methods/MethodsAccordion";
import ArtistGrid from "@/components/artists/ArtistGrid";
import ScrollySentiment from "@/components/sections/ScrollySentiment";
import TopicsSection from "@/components/sections/TopicsSection";
import TimelineSection from "@/components/sections/TimelineSection";
import Conclusions from "@/components/sections/Conclusions";

export default function Home() {
  const { corpus, artists, tracks, topics, timeline } = loadAllData();

  return (
    <div>
      <LegalBanner />

      <div className="page-wrap">
        <SideNav />

        <main id="main-content" aria-label="Лонгрид: Музыка после отъезда">
          <Hero corpus={corpus} />

          <SectionIntro />

          <MethodsAccordion />

          <ArtistGrid artists={artists} />

          <ScrollySentiment tracks={tracks} artists={artists} />

          <TopicsSection topics={topics} />

          <TimelineSection timeline={timeline} />

          <Conclusions />
        </main>
      </div>
    </div>
  );
}
