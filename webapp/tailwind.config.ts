import type { Config } from "tailwindcss";

// Design tokens for the Quran Video Generator admin webapp.
//
// Aesthetic direction: a precise, archive-flavoured operations tool —
// think broadcast control room meets editorial layout. Disciplined
// hairlines, restrained oxblood accent, IBM Plex family throughout.
// The signature element is the slice-timeline on the execution detail
// page; everything else stays quiet so that one element can be memorable.
const config: Config = {
  content: ["./src/**/*.{ts,tsx,js,jsx,mdx}"],
  theme: {
    extend: {
      colors: {
        // Surface
        paper: "#FAF8F4",       // warm ivory (not the cliché cream)
        ink: "#0F1419",         // near-black, slightly cool
        rule: "#1F2A30",        // deep blue-grey for hairlines
        mute: "#6B6256",        // warm grey for secondary text
        // Status
        accent: "#A8331B",      // restrained oxblood — used sparingly
        success: "#3B6E47",     // deep forest green
        warn: "#8A5A00",        // amber
        failed: "#7A1C1C",      // deep red
      },
      fontFamily: {
        // IBM Plex family throughout — open-source, distinctive, reads as
        // "technical archive" rather than generic SaaS.
        sans: ["var(--font-plex-sans)", "system-ui", "sans-serif"],
        serif: ["var(--font-plex-serif)", "Georgia", "serif"],
        mono: ["var(--font-plex-mono)", "ui-monospace", "monospace"],
      },
      fontSize: {
        // Tight numeric scale so data tables stay legible at small sizes.
        "2xs": ["0.6875rem", { lineHeight: "1rem" }],
      },
      letterSpacing: {
        "wide-2": "0.08em",
        "wide-3": "0.14em",
      },
      borderWidth: {
        hairline: "1px",
      },
      maxWidth: {
        "8xl": "88rem",
      },
    },
  },
  plugins: [],
};

export default config;
