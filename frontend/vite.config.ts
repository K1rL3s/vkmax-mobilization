import react from "@vitejs/plugin-react";
import { fileURLToPath } from "node:url";
import { defineConfig, loadEnv } from "vite";

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");

  return {
    plugins: [react()],
    resolve: {
      alias: {
        "@": fileURLToPath(new URL("./src", import.meta.url)),
      },
    },
    css: {
      modules: {
        localsConvention: "camelCase",
        generateScopedName: "[name]__[local]___[hash:base64:5]",
      },
    },
    server: {
      allowedHosts: true,
      proxy: {
        "/api": {
          target: env.DEV_API_TARGET ?? "http://localhost",
          changeOrigin: true,
        },
        "/tiles/ofm": {
          target: "https://tiles.openfreemap.org",
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/tiles\/ofm/, ""),
        },
        "/tiles/osm": {
          target: "https://tile.openstreetmap.org",
          changeOrigin: true,
          headers: { "User-Agent": "zheka-kommunalkin/1.0 (dev)" },
          rewrite: (path) => path.replace(/^\/tiles\/osm/, ""),
        },
      },
    },
  };
});
