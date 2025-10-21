# ChiloDisco 前端（Vite + Vue 3）

这是 ChiloDisco 的正式 Vue 工程版前端。构建后 Flask 会自动优先提供此构建产物（无需改动后端路由）。

## 目录结构
```
ChiloDisco/frontend
├─ index.html            # Vite 入口（生产构建会复制到 dist）
├─ src/
│  ├─ main.js
│  └─ App.vue            # 已迁移现有功能：/api/logs 轮询、逐行着色、无滚动条布局
├─ package.json
├─ vite.config.js
└─ README.md
```

注意：样式直接复用后端的 `/static/css/styles.css`，构建后仍从 Flask 提供该 CSS。

## 开发
1. 安装 Node.js（建议 18+）。
2. 安装依赖：
   ```bash
   npm i
   ```
3. 开发模式：
   ```bash
   npm run dev
   ```
   默认端口 5173，可在浏览器打开 http://127.0.0.1:5173 进行开发联调。

## 生产构建
```bash
npm run build
```
完成后生成 `frontend/dist`。后端 Flask 会检测 `ChiloDisco/frontend/dist/index.html` 是否存在，若存在：
- 访问 `http://127.0.0.1:5000/` 将直接返回构建产物的 `index.html`。
- `/assets/*` 由 Flask 代理到 `dist/assets`。
- 其他 API 路径不变：`/api/logs`、`/health`。

若未构建（没有 dist），Flask 会回退到老的模板版（CDN Vue）页面，不影响开发过程。

## 与后端接口
- 轮询 `/api/logs` 获取：
  ```json
  {
    "now": "<ISO时间>",
    "logs": {
      "<LOG_KEY>": {
        "path": "<绝对路径>",
        "exists": true,
        "size": 1234,
        "mtime": "<ISO时间>",
        "lines": [ { "s": "行文本", "t": "首次看到的ISO时间" }, ... ]
      },
      ...
    }
  }
  ```
- 前端按每行的 t 或行内时间戳着色；无滚动条，仅渲染可视高度能容纳的最后 N 行。

## 常见问题
- 首行“诡异空格”：已在前端对每行做了 BOM 去除与行首空白去除；若日志本身需要保留缩进，可在 App.vue 的 `colorizeLineObj` 中调整去空白策略。
