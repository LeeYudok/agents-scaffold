// 화면 번들: 에디터(<base>/)·대본 음성(<base>/player)·영상 비교(<base>/compare) 세 페이지. 서버(src/server)가 그대로 서빙한다.
// base 는 레포 설정(script-editor.json base)이라 setup 이 `vite build --base <base>/ --outDir <인스턴스 dist>` 로 넘긴다.
// 화면의 API·미디어 주소는 상대 경로라 base 와 무관하다.
/// <reference types="vitest/config" />
import { resolve } from "node:path";
import { defineConfig } from "vite";

const root = resolve(import.meta.dirname, "src/client");

export default defineConfig({
  root,
  build: {
    outDir: resolve(import.meta.dirname, "dist"),
    emptyOutDir: true,
    rollupOptions: {
      input: {
        editor: resolve(root, "editor/index.html"),
        player: resolve(root, "player/index.html"),
        compare: resolve(root, "compare/index.html"),
      },
    },
  },
  test: {
    root: import.meta.dirname,
    include: ["src/**/*.test.ts"],
  },
});
