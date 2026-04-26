# Frontend (React + Vite)

## Quick start

1. Install dependencies:
   - `npm install`
2. Start dev server:
   - `npm run dev`

## Scripts

- `npm run dev` – start development server
- `npm run build` – production build
- `npm run preview` – preview production build
- `npm run lint` – lint the codebase

## Rough folder structure

```text
frontend/
├─ public/
├─ src/
│  ├─ components/
│  │  ├─ charts/
│  │  ├─ kpi/
│  │  └─ layout/
│  ├─ data/
│  ├─ features/
│  │  └─ filters/
│  ├─ hooks/
│  ├─ pages/
│  ├─ services/
│  ├─ styles/
│  ├─ utils/
│  ├─ App.jsx
│  └─ main.jsx
├─ .env.example
├─ eslint.config.js
├─ index.html
├─ package.json
└─ vite.config.js
```

## Notes

- If `VITE_API_BASE_URL` is not set, the app uses local mock data.
- Charts are implemented with `d3`.
