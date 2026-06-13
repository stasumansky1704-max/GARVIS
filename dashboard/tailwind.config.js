/** @type {import("tailwindcss").Config} */
export default {
  content: ["./src/living-core/**/*.{ts,tsx}"],
  theme: { extend: {} },
  // Embedded in a non-Tailwind dashboard: scope every utility under
  // .living-core-root AND raise its specificity so the dashboard global
  // stylesheet cannot override the living-core layout utilities.
  important: ".living-core-root",
  // preflight OFF so Tailwind base reset never touches the existing dashboard
  corePlugins: { preflight: false },
};
