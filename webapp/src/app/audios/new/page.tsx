import { PageHeader } from "@/components/PageHeader";
import { AudioForm } from "@/components/AudioForm";
import { BackLink } from "@/components/BackLink";

export default function NewAudioPage() {
  return (
    <>
      <PageHeader
        eyebrow="MEDIA / AUDIOS"
        title="Add audio"
        meta="Register a Quran recitation by its remote URL. The pipeline downloads it on demand."
      />
      <div className="px-8 py-10 max-w-2xl">
        <AudioForm />
        <div className="mt-8 text-sm">
          <BackLink href="/audios">← back to audios</BackLink>
        </div>
      </div>
    </>
  );
}
