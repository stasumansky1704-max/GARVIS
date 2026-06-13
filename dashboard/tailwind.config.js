/** @type {import("tailwindcss").Config} */
export default {
  content: ["./src/living-core/**/*.{ts,tsx}"],
  theme: { extend: {} },
  // corePlugins.preflight OFF so Tailwind base reset does NOT touch the existing dashboard CSS
  corePlugins: { preflight: false },
};
