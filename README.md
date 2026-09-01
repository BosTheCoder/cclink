# cclink

Demo deployed via [demo-tools](https://github.com/BosTheCoder/demo-tools).

- **Stack:** html
- **Deploy target:** pages
- **Local dev:** `just dev` — runs the production image, so a source change needs a rebuild. For hot reload, add a `compose.dev.yml` that bind-mounts your source and runs your dev server; `just dev` layers it automatically.
- **Deploy:** `just deploy`
- **Live URLs:**
  - https://cclink.fly.dev (always works)
- https://cclink.demos.buildwithbos.com
Hostnames come from the `hostnames` list in `.demo-template-version`; `just deploy`
  points each one at this app's IPs and provisions a cert. Set it to the real
  domains for an app that owns them, or `[]` to deploy without touching DNS.
- **Stop / start / destroy:** `just stop` / `just start` / `just destroy`
- **Update infra files:** `just sync`
