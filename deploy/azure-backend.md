# Azure Backend Deployment (FastAPI)

This guide migrates backend deployment from Render to Azure while keeping frontend on Vercel.

Recommended target: Azure Container Apps (ACA) with Azure Container Registry (ACR).

Optional helper script:

```powershell
./deploy/azure-deploy-backend.ps1 `
	-ResourceGroup "researchhub-rg" `
	-Location "eastus" `
	-AcrName "researchhubacr" `
	-ContainerAppEnv "researchhub-aca-env" `
	-ContainerAppName "researchhub-backend"
```

## 1) Prerequisites

- Azure CLI installed and logged in (`az login`)
- Subscription selected (`az account set --subscription <subscription-id-or-name>`)
- Access to this repository and current backend env values

## 2) Create Azure Resources (one-time)

Set names:

```powershell
$RG = "researchhub-rg"
$LOCATION = "eastus"
$ACR = "researchhubacr"
$ACA_ENV = "researchhub-aca-env"
$APP = "researchhub-backend"
```

Create resources:

```powershell
az group create --name $RG --location $LOCATION
az acr create --resource-group $RG --name $ACR --sku Basic --admin-enabled true
az extension add --name containerapp --upgrade
az provider register --namespace Microsoft.App
az provider register --namespace Microsoft.OperationalInsights
az containerapp env create --name $ACA_ENV --resource-group $RG --location $LOCATION
```

## 3) Build and Push Backend Image

From repository root:

```powershell
az acr build --registry $ACR --image researchhub-backend:latest --file backend/Dockerfile backend
```

## 4) Deploy the Container App

```powershell
az containerapp create `
	--name $APP `
	--resource-group $RG `
	--environment $ACA_ENV `
	--ingress external `
	--target-port 8000 `
	--registry-server "$ACR.azurecr.io" `
	--image "$ACR.azurecr.io/researchhub-backend:latest"
```

Get app URL:

```powershell
$APP_URL = az containerapp show --name $APP --resource-group $RG --query properties.configuration.ingress.fqdn -o tsv
"https://$APP_URL"
```

## 5) Configure Environment Variables and Secrets

Use the same backend env contract currently used on Render.

Start with template: `deploy/azure-backend.env.example`

Important values to update for Azure:

- `BACKEND_URL=https://<your-aca-fqdn>`
- `GOOGLE_REDIRECT_URI=https://<your-aca-fqdn>/auth/google/callback`
- Keep `AUTH_COOKIE_SAMESITE=none`
- Keep `AUTH_COOKIE_SECURE=1`

Set values in ACA (example):

```powershell
az containerapp update `
	--name $APP `
	--resource-group $RG `
	--set-env-vars APP_ENV=production AUTH_COOKIE_SAMESITE=none AUTH_COOKIE_SECURE=1
```

For secrets, use Container App secrets and reference them in env vars.

## 6) Update Frontend (Vercel)

Set Vercel env vars and redeploy frontend:

- `VITE_API_URL=https://<your-aca-fqdn>`
- `VITE_API_BASE=https://<your-aca-fqdn>`

## 7) Health Check Validation

- Liveness: `GET /health/live`
- Readiness: `GET /health/ready` (if implemented)
- Swagger docs: `GET /docs`

Quick smoke check:

```powershell
curl "https://<your-aca-fqdn>/health/live"
```

## 8) Rollout Strategy from Render

1. Deploy Azure backend with all env vars and secrets.
2. Verify health and critical auth/AI routes.
3. Update Vercel API URL to Azure URL and redeploy frontend.
4. Validate login, chat, and paper workflows in production.
5. Keep Render running briefly as rollback, then decommission.

## 9) GitHub Actions Auto-Deploy (optional, recommended)

Workflow file:

- `.github/workflows/backend-azure-deploy.yml`

Trigger behavior:

- Runs on push to `main` when `backend/**` changes
- Supports manual run via `workflow_dispatch`

### Required GitHub repository secrets

- `AZURE_CREDENTIALS` (JSON output from Azure service principal creation)
- `AZURE_RESOURCE_GROUP`
- `AZURE_CONTAINER_APP_NAME`
- `AZURE_ACR_NAME`

### Create service principal for GitHub Actions

```powershell
az ad sp create-for-rbac `
	--name "github-actions-researchhub-backend" `
	--role contributor `
	--scopes /subscriptions/<subscription-id>/resourceGroups/<rg-name> `
	--sdk-auth
```

Use the full JSON output as the `AZURE_CREDENTIALS` secret.

### What the workflow does

1. Logs into Azure with `azure/login@v2`
2. Builds backend image in ACR with tag `${GITHUB_SHA}`
3. Updates Azure Container App to the new image
4. Prints deployed image and backend URL in job logs

