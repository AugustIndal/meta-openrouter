import { defineConfig } from 'vite';
export default defineConfig({
  server: {
    host: '127.0.0.1',
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8770',
        changeOrigin: true,
        configure(proxy) {
          proxy.on('proxyReq', (request, incoming) => {
            if (['http://127.0.0.1:5173', 'http://localhost:5173'].includes(incoming.headers.origin)) {
              request.setHeader('Origin', 'http://127.0.0.1:8770');
            }
          });
        },
      },
    },
  },
  build: { outDir: 'dist' },
});
