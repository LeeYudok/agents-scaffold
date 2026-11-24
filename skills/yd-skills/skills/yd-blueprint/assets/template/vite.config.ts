import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// 기본 포트(5173)의 /blueprint/ 에 뜬다. 포트가 차 있으면 vite 가 다음 포트를 잡고 실제 주소를 출력한다.
// host 를 127.0.0.1 로 고정한다: 기본 localhost 는 [::1] 에 묶여, 127.0.0.1:5173 의 다른 vite 와 포트가 안 겹쳐 둘이 같이 뜬다.
// 브라우저 자동 열기는 BROWSER=none 으로 끈다.
// 캐시는 프로젝트 폴더의 .vite 에 둔다: --deps-dir 로 node_modules 를 여러 청사진이 함께 쓰면 기본 위치(node_modules/.vite)가 섞인다.
export default defineConfig({
  base: "/blueprint/",
  cacheDir: ".vite",
  plugins: [
    react(),
    {
      name: "blueprint-root-redirect",
      configureServer(server) {
        server.middlewares.use((req, res, next) => {
          if (req.url !== "/") return next();
          res.statusCode = 302;
          res.setHeader("Location", "/blueprint/");
          res.end();
        });
      },
    },
  ],
  server: { host: "127.0.0.1", open: "/blueprint/" },
});
