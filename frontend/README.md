# DeliveryCart frontend

This folder hosts the existing UI documents under `public/` without converting
their markup or inline JavaScript. The Next-compatible app shell is configured
with vinext and Cloudflare Workers.

## Local development

```powershell
Set-Location frontend
Copy-Item .env.example .env.local
npm ci
npm run dev
```

Set `NEXT_PUBLIC_API_URL` to the Django server origin in `.env.local`. The
default is `http://127.0.0.1:8000`. The Next config proxies `/api/*` and
`/media/*` through that URL, so the browser keeps using the existing relative
paths and session cookies remain same-origin from the page's point of view.

## Cloudflare Workers

Cloudflare's current docs recommend vinext for new Next.js projects on Workers.
`NEXT_PUBLIC_API_URL` must be present in the Cloudflare build environment because
the external API rewrites are configured at build time. Use `npm run build` to
build and `npm run start` to preview in the Workers runtime. `npm run deploy`
deploys to Cloudflare and is intentionally not run from this workspace.
