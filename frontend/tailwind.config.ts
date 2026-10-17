import type { Config } from "tailwindcss";

const v = (name: string) => `var(--${name})`;

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        paper: { DEFAULT: v("paper"), 2: v("paper-2") },
        surface: v("surface"),
        ink: { DEFAULT: v("ink"), 2: v("ink-2"), 3: v("ink-3") },
        rule: { DEFAULT: v("rule"), 2: v("rule-2") },
        green: { DEFAULT: v("green"), 2: v("green-2"), wash: v("green-wash") },
        oxblood: { DEFAULT: v("oxblood"), wash: v("oxblood-wash") },
        brass: { DEFAULT: v("brass"), wash: v("brass-wash") },
        mark: v("mark"),
      },
      fontFamily: { serif: v("f-serif"), sans: v("f-sans"), mono: v("f-mono") },
      boxShadow: { ring: v("shadow"), lift: v("shadow-lift") },
      transitionTimingFunction: { DEFAULT: v("ease") },
    },
  },
  plugins: [],
};
export default config;
