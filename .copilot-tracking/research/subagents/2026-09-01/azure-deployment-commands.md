---
title: Azure Deployment Command Research
description: Local evidence for frontend-only and backend-only Azure deployment commands
ms.date: 2026-09-01
ms.topic: reference
---

## Status

Complete

## Research Questions

* What exact existing command deploys only the frontend on the current branch and local environment?
* What exact existing command deploys only backend container changes?
* Which Azure resources do those commands target, and what does each command change?
* Which local and live validation commands are already documented or scripted?
* Is the frontend hosted by Azure App Service and the backend hosted by Azure Container Apps?

## Constraints

* Research local files only
* Do not run Azure CLI, Azure Developer CLI, or deployment commands
* Do not modify application or infrastructure source files

## Initial Evidence

* `azure.yaml` defines service `web` with `host: appservice` and resource name `${AZURE_WEB_APP_NAME}`.
* `azure.yaml` defines service `api` with `host: containerapp` and resource name `${AZURE_CONTAINER_APP_NAME}`.
* `planetary-explorer/azure.yaml` contains the same service-to-host mapping for commands run from that subdirectory.

## Current Branch And Environment

* Git branch: `feat/dynamic-map-layer-selector`
* Git upstream: `fork/feat/dynamic-map-layer-selector`
* Default local Azure Developer CLI environment: `earthcopilot`
* Subscription: `ME-MngEnvMCAP252498-chenalex-1` (`a0c62bdd-d642-4fdb-b372-ae041cf83ce3`)
* Tenant: `711a9076-1115-4c36-b7b4-82b4f3a05f6f`
* Location: `eastus2`
* Resource group: `rg-earthcopilot`

The deployment definitions and per-service scripts have no working-tree diff on
the current branch. The working tree does contain application source changes,
including both `container-app` and `web-ui` files. Both deployment scripts build
from the working tree, so they would publish all included uncommitted changes.

## Confirmed Hosting Topology

| Component | Manifest service | Azure host | Existing target |
|-----------|------------------|------------|-----------------|
| React frontend | `web` | Azure App Service | `app-earthcopilot-e1bb5a9c` |
| FastAPI backend | `api` | Azure Container Apps | `ca-earthcopilot-api` |
| Backend image | Not a service | Azure Container Registry | `cr44gnuvaloryac.azurecr.io/planetaryexplorer-api` |

The frontend URL is
`https://app-earthcopilot-e1bb5a9c.azurewebsites.net/`. The backend URL is
`https://ca-earthcopilot-api.thankfulplant-49ee7bc3.eastus2.azurecontainerapps.io/`.

## Target Guard

The scripts use the Azure CLI's current account and do not accept a subscription
parameter. Assert the target immediately before any future write:

```powershell
$expectedSubscription = 'a0c62bdd-d642-4fdb-b372-ae041cf83ce3'
$expectedTenant = '711a9076-1115-4c36-b7b4-82b4f3a05f6f'
$account = az account show --output json | ConvertFrom-Json
if ($account.id -ne $expectedSubscription -or $account.tenantId -ne $expectedTenant) {
    throw 'Azure account does not match the earthcopilot deployment target.'
}
```

This command is documented for future execution only. It was not run during
this research.

## Safest Frontend-Only Command

Run from the repository root after reviewing the working-tree scope:

```powershell
pwsh -NoProfile -File .\planetary-explorer\web-ui\deploy-frontend.ps1 `
    -ResourceGroup 'rg-earthcopilot' `
    -AppServiceName 'app-earthcopilot-e1bb5a9c' `
    -ApiBaseUrl 'https://ca-earthcopilot-api.thankfulplant-49ee7bc3.eastus2.azurecontainerapps.io'
```

This is safer than auto-discovery because every write target and the build-time
API origin are explicit. It installs npm dependencies, builds the production
Vite bundle with the live Container App origin, adds the dependency-free Node
SPA host files to `dist`, creates a Linux-compatible ZIP, and runs
`az webapp deploy --type zip` against the existing App Service. It replaces App
Service site content only. It does not provision infrastructure or update the
backend Container App.

Do not add `-SkipBuild` unless the existing `dist` directory was independently
validated against the exact production API origin.

## Safest Backend Container Command

Run from the repository root after reviewing the working-tree scope:

```powershell
pwsh -NoProfile -File .\planetary-explorer\container-app\deploy-backend.ps1 `
    -ResourceGroup 'rg-earthcopilot' `
    -ContainerAppName 'ca-earthcopilot-api' `
    -AppServiceName 'app-earthcopilot-e1bb5a9c' `
    -Registry 'cr44gnuvaloryac'
```

This command builds the repository's `Dockerfile.complete` remotely with the
`planetary-explorer` directory as context. It pushes a timestamped
`planetaryexplorer-api` tag and updates `latest`, then updates the existing API
Container App. The image contains the FastAPI application and a built copy of
the React frontend, although the public frontend remains the App Service.

The Container App update is broader than an image pointer change. The script
preserves current environment values and secret references, sets required
defaults, repairs CORS when needed, updates the image and environment in one
operation, sets ingress target port 8080, enables sticky sessions, and runs
`scripts/configure_api_postdeploy.py`. That postdeploy step reconciles optional
service settings when their environment outputs are present and rewrites the
API liveness and readiness probes. It creates a new Container Apps revision but
does not apply Bicep or provision resources.

Do not add `-SkipBuild`: that path deploys the mutable `latest` tag.

## Azure Developer CLI Alternatives

The root and nested manifests support these service-scoped commands:

```powershell
azd deploy web
azd deploy api
```

The default environment is currently `earthcopilot`, and manifest
`resourceName` values resolve to the targets above. Neither command invokes the
custom `up` workflow or provisions infrastructure.

For this environment, `azd deploy web` is not the preferred frontend path.
Repository memory records that it previously produced a bundle with the
localhost API fallback despite the manifest environment mapping. The explicit
frontend script was adopted to guarantee the live API origin. The explicit
backend script is also preferable when preserving the existing Container App
environment and runtime settings is required.

`planetary-explorer/deploy-all.ps1 -Target frontend` and `-Target backend` are
valid wrappers, but they perform additional discovery. The direct scripts with
explicit target arguments have less ambiguity. `QUICK_DEPLOY.md` incorrectly
states that the per-service scripts accept `-EnvironmentName`; neither current
PowerShell parameter block defines that parameter.

## Validation Commands

### Scope And Target Checks

```powershell
git branch --show-current
git status --short
git diff --check
Get-Content .\.azure\config.json
```

Expected branch and environment are `feat/dynamic-map-layer-selector` and
`earthcopilot`. Review all modified and untracked files before deployment
because the build contexts use the working tree.

### Frontend Before Deployment

```powershell
npm --prefix .\planetary-explorer\web-ui run test:run
npm --prefix .\planetary-explorer\web-ui run test:deployment
$env:VITE_API_BASE_URL = 'https://ca-earthcopilot-api.thankfulplant-49ee7bc3.eastus2.azurecontainerapps.io'
npm --prefix .\planetary-explorer\web-ui run build
Select-String -Path .\planetary-explorer\web-ui\dist\assets\*.js `
    -SimpleMatch $env:VITE_API_BASE_URL -Quiet
Remove-Item Env:VITE_API_BASE_URL
```

The bundle-origin check must return `True`.

### Backend Before Deployment

```powershell
Push-Location .\planetary-explorer\container-app
uv run pytest -q
uv run python -m compileall -q .
Pop-Location
Invoke-Pester .\planetary-explorer\scripts\tests\deploy-backend.Tests.ps1
```

### Live HTTP Checks

```powershell
Invoke-WebRequest `
    'https://app-earthcopilot-e1bb5a9c.azurewebsites.net/' `
    -Method Get -UseBasicParsing
Invoke-WebRequest `
    'https://ca-earthcopilot-api.thankfulplant-49ee7bc3.eastus2.azurecontainerapps.io/api/health' `
    -Method Get -UseBasicParsing
```

Both should return HTTP 200. After a frontend publish, also inspect the served
JavaScript bundle and confirm it contains the exact production API origin.

### Live Azure State Checks

These commands are documented for future validation and were not run:

```powershell
az webapp show `
    --resource-group 'rg-earthcopilot' `
    --name 'app-earthcopilot-e1bb5a9c' `
    --query '{state:state,host:defaultHostName}' -o table

az containerapp show `
    --resource-group 'rg-earthcopilot' `
    --name 'ca-earthcopilot-api' `
    --query '{status:properties.runningStatus,revision:properties.latestRevisionName,fqdn:properties.configuration.ingress.fqdn}' `
    -o table

az containerapp logs show `
    --resource-group 'rg-earthcopilot' `
    --name 'ca-earthcopilot-api' --follow
```

## References

* `azure.yaml`
* `planetary-explorer/azure.yaml`
* `.azure/config.json`
* `.azure/earthcopilot/.env` (non-secret target fields only)
* `.azure/deployment-plan.md`
* `QUICK_DEPLOY.md`
* `planetary-explorer/deploy-all.ps1`
* `planetary-explorer/web-ui/deploy-frontend.ps1`
* `planetary-explorer/web-ui/package.json`
* `planetary-explorer/web-ui/vite.config.ts`
* `planetary-explorer/web-ui/scripts/prepare-deployment.cjs`
* `planetary-explorer/web-ui/deployment/server.cjs`
* `planetary-explorer/container-app/deploy-backend.ps1`
* `planetary-explorer/container-app/Dockerfile.complete`
* `planetary-explorer/scripts/tests/deploy-backend.Tests.ps1`
* `scripts/configure_api_postdeploy.py`
* Repository memory `/memories/repo/azure-deployment.md`
* Repository memory `/memories/repo/workspace.md`

## Follow-On Questions

None required for the requested scope.

## Clarifying Questions

None.
