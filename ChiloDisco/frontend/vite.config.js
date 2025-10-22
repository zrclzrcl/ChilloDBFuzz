import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// 开发环境下通过代理将 API 与静态资源转发到 Flask (http://127.0.0.1:5000)
export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:5000',
        changeOrigin: true,
      },
      '/health': {
        target: 'http://127.0.0.1:5000',
        changeOrigin: true,
      },
      '/static': {
        target: 'http://127.0.0.1:5000',
        changeOrigin: true,
      },
      '/favicon.ico': {
        target: 'http://127.0.0.1:5000',
        changeOrigin: true,
      },
      // 若后端已构建前端产物，也允许调试访问 /assets
      '/assets': {
        target: 'http://127.0.0.1:5000',
        changeOrigin: true,
      },
      '/plot': {
        target: 'http://127.0.0.1:5000',
        changeOrigin: true,
      },
      '/downloads': {
        target: 'http://127.0.0.1:5000',
        changeOrigin: true,
      }
    }
  }
})
