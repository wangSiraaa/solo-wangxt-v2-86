import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

// 构建产物交给 Django（staticfiles）托管：
// 资源前缀 /static/，index.html 由 Django TemplateView 渲染
export default defineConfig({
  plugins: [vue()],
  base: "/static/",
  build: {
    outDir: "../backend/frontend_dist",
    emptyOutDir: true,
  },
  server: {
    port: 5173,
    proxy: {
      "/api": "http://127.0.0.1:8000",
    },
  },
});
