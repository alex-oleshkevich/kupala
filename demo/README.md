# Kupala demo

Create `demo/.env` with a local API key:

```console
DEMO_API_KEY=local-demo-key
```

The settings model loads that file when the application starts:

```console
just dev
```

The generated API document is available at `http://localhost:7000/api/v1/docs`. The product deletion
example performs the same check it publishes in OpenAPI:

```console
curl -X DELETE http://localhost:7000/api/v1/products/DSK-01 \
  -H 'X-Demo-Key: local-demo-key'
```

The Basic-auth example uses `demo` as the username and the same local key as its password:

```console
curl -u demo:local-demo-key http://localhost:7000/api/v1/basic
```

`DEMO_API_KEY` is only a local demonstration credential. Use a secret manager and a real authenticator
for deployed applications.
