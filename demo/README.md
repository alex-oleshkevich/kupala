# Kupala demo

Create `demo/.env` with a local API key:

```console
DEMO_API_KEY=local-demo-key
```

The settings model loads that file when the application starts:

```console
just dev
```

Application middleware requires Basic authentication for every web and API route. Browsing to the generated API
document at `http://localhost:7000/api/v1/docs` opens the browser's login prompt; use `demo` as the username and the
local API key as the password. The same requirement is published for every operation in OpenAPI:

```console
curl -u demo:local-demo-key http://localhost:7000/api/v1/products
```

Product deletion also requires its route-specific API key, so the generated operation publishes both requirements:

```console
curl -X DELETE -u demo:local-demo-key http://localhost:7000/api/v1/products/DSK-01 \
  -H 'X-Demo-Key: local-demo-key'
```

`DEMO_API_KEY` is only a local demonstration credential. Use a secret manager and a real authenticator
for deployed applications.
