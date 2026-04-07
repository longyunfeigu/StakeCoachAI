# Stakeholder Chat Frontend

React + TypeScript + Vite 前端项目。

## 开发

```bash
npm run dev     # 启动开发服务器 (http://localhost:5173)
npm run build   # 生产构建
```

## 配置

- `.env` 中 `VITE_API_URL` 设置后端地址（默认 `http://localhost:8000`）
- `vite.config.ts` 将 `/api` 请求代理到后端
