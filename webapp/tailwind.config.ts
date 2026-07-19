import type { Config } from "tailwindcss";

/**
 * Archival palette — warm parchment, ink, oxblood accent.
 *
 * This is NOT a dark SaaS dashboard. The subject is a Quran media pipeline
 * (recitations + scenery videos) and the operators are curators. The
 * palette is borrowed from typeset scholarly journals and manuscript
 * catalogs: cream paper, warm near-black ink, deep oxblood for emphasis
 * (the only saturated colour on the page, used like a calligrapher's
 * marginalia), and a forest-green / amber / crimson trio for status.
 */
const config: Config = {
  content: ["./src/**/*.{ts,tsx,js,jsx,mdx}"],
  theme: {
    extend: {
      colors: {
        paper: "#FAF7F0",        // warm parchment background
        paperRaised: "#F4EFE3",  // slightly darker for raised surfaces (cards, sidebar)
        ink: "#1F1B16",          // warm near-black body text
        inkSoft: "#3D352B",      // secondary body
        mute: "#6B6258",         // warm gray, secondary text
        rule: "#DDD5C7",         // hairline rules
        ruleSoft: "#ECE5D6",     // very subtle hairline for inside-list rows
        accent: "#7C2D12",       // oxblood — emphasis only
        accentSoft: "#B45309",   // amber — used very sparingly
        success: "#2D5A3D",      // deep forest green
        warn: "#B45309",         // amber
        failed: "#991B1B",       // deep crimson
      },
      fontFamily: {
        sans: ["var(--font-plex-sans)", "system-ui", "sans-serif"],
        serif: ["var(--font-plex-serif)", "Georgia", "serif"],
        mono: ["var(--font-plex-mono)", "ui-monospace", "monospace"],
      },
      fontSize: {
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
