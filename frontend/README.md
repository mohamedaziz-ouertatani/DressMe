# DressMe app (frontend)

React 19 + Vite + TypeScript + Tailwind 4. Talks to the FastAPI backend in `../backend` through the `/api` dev proxy.

```bash
npm install
npm run dev      # http://localhost:5173 (API on :8000)
npm run build    # type-check + production build
npm run lint
```

- `src/pages/`: the app screens; `src/admin/`: the admin dashboard
- `src/ui/`: ticket, stamp, field, chip and photo primitives
- `src/i18n/`: English, French, Arabic (RTL), with plurals
- Design rules: `../DESIGN.md`. Product brief: `../PRODUCT.md`.
