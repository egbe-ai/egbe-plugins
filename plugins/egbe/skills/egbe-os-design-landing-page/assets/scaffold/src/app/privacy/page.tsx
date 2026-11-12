import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Privacy",
  description: "How we use analytics and session recordings.",
};

export default function PrivacyPage() {
  return (
    <main className="mx-auto max-w-2xl space-y-6 px-6 py-16">
      <h1 className="text-3xl font-semibold">Privacy</h1>
      <section className="space-y-3">
        <h2 className="text-xl font-semibold">Analytics and session recordings</h2>
        <p>
          We use analytics and masked session recordings to understand how people
          use this product, identify confusing steps, and improve the experience.
          Recordings capture page interactions such as clicks, scrolling, and
          navigation. This is a replay of activity within the site, not a recording
          of your camera, microphone, or other applications.
        </p>
        <p>
          Recording is enabled for all sessions, with a maximum duration of 30
          minutes per recording. We apply input masking to recordings.
        </p>
      </section>
    </main>
  );
}
