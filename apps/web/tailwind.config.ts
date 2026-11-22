import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        canvas: "#f3f4f1",
        panel: "#ffffff",
        ink: "#182023",
        muted: "#64706f",
        line: "#d9ddda",
        accent: "#0f766e",
        "accent-soft": "#e4f1ee",
        signal: "#b45309",
        "signal-soft": "#fbefe0",
        danger: "#b42318",
        "danger-soft": "#fce9e7",
      },
      boxShadow: {
        panel: "0 1px 2px rgba(24, 32, 35, 0.05)",
      },
    },
  },
  plugins: [],
};

export default config;
