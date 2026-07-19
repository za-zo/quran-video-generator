import Link from "next/link";
import { PageHeader } from "@/components/PageHeader";
import { AudioForm } from "@/components/AudioForm";

export default function NewAudioPage() {
  return (
    <>
      <PageHeader
        eyebrow="MEDIA / AUDIOS"
        title="Add audio"
        meta="Register a Quran recitation by its remote URL. The pipeline downloads it on demand."
      />
      <div className="px-8 py-8 max-w-2xl">
        <AudioForm />
        <div className="mt-4 text-sm">
          <Link href="/audios" className="quiet-link">
            ← back to audios
          </Link>
        </div>
      </div>
    </>
  );
}
