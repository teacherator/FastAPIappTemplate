import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  base: "/portal/", // IMPORTANT so asset URLs work when served under /portal
});
