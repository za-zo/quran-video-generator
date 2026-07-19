import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx,js,jsx,mdx}"],
  theme: {
    extend: {
      colors: {
        paper: "#121212",       // Dark gray background
        ink: "#E0E0E0",         // Main text light gray
        rule: "#2A2A2A",        // Hairlines
        mute: "#888888",        // Secondary text
        accent: "#E53935",      // Brighter red for dark mode
        success: "#43A047",
        warn: "#FFB300",
        failed: "#EF5350",
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
