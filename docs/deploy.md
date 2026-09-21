# Hosting

Nomina's Streamable HTTP mode is stateless, keeps no data, and needs no secrets, so it runs
on any container platform that terminates TLS and can health-check `GET /healthz`. The
container listens on `PORT` (default 8000) and rejects requests whose `Host` header is not
`PUBLIC_HOST`, `localhost`, or `127.0.0.1`.

## Current deployment (Render)

`render.yaml` at the repository root is deployed as a Render Blueprint from the public
repository: service `nomina-mcp`, Docker runtime, free plan, health check `/healthz`, public
host taken from Render's `RENDER_EXTERNAL_HOSTNAME`. Live at
`https://nomina-mcp.onrender.com/mcp`. The release workflow triggers a redeploy through a
Render deploy hook after each tagged release. Free instances sleep after 15 idle minutes and
wake in about a minute; a paid instance removes that. There is no edge rate limiting yet.

The Fly.io and Cloud Run commands below follow each platform's documentation and have not
been run for Nomina; `fly.toml` is checked for TOML syntax only.

## Fly.io

`fly.toml` at the repository root is ready to use:

```sh
fly launch --copy-config --no-deploy
fly secrets set PUBLIC_HOST=mcp.example.com
fly deploy
fly certs add mcp.example.com
```

Then point `mcp.example.com` at the app (`CNAME <app>.fly.dev`) and connect clients to
`https://mcp.example.com/mcp`.

## Google Cloud Run

```sh
gcloud run deploy nomina-mcp \
  --source . --region us-east1 --allow-unauthenticated \
  --port 8000 --set-env-vars PUBLIC_HOST=mcp.example.com \
  --min-instances 0 --max-instances 3 --concurrency 50
gcloud run domain-mappings create --service nomina-mcp --domain mcp.example.com
```

## Before exposing it publicly

- **Rate limiting.** The server has no authentication and every request can reach Yahoo
  Finance's public endpoints from one egress address. Put a per-client limit at the edge
  (for a Cloudflare-fronted domain: a Rate Limiting rule on `/mcp`, e.g. 60 requests per
  minute per IP). The built-in 60 s response cache absorbs repeated identical requests but
  is not an abuse control.
- **Provider terms.** Hosting concentrates automated collection on one operator; review
  Yahoo's terms (see [Data sources and limits](data-sources/)) before operating at scale or
  for others.
- **Logs.** Nomina writes no request logs; the platform and any proxy in front of it will.
  The [privacy policy](privacy/) already says so.
- **Health.** `GET /healthz` returns `ok`; use it for the platform check. `POST /mcp` with
  an `initialize` request confirms the MCP layer.
