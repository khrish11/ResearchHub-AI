param(
    [Parameter(Mandatory = $true)]
    [string]$ResourceGroup,

    [Parameter(Mandatory = $true)]
    [string]$Location,

    [Parameter(Mandatory = $true)]
    [string]$AcrName,

    [Parameter(Mandatory = $true)]
    [string]$ContainerAppEnv,

    [Parameter(Mandatory = $false)]
    [string]$ContainerAppName = "researchhub-backend",

    [Parameter(Mandatory = $false)]
    [string]$ImageTag = "latest"
)

$ErrorActionPreference = "Stop"

Write-Host "[1/5] Creating resource group..."
az group create --name $ResourceGroup --location $Location | Out-Null

Write-Host "[2/5] Creating ACR (if not exists)..."
az acr create --resource-group $ResourceGroup --name $AcrName --sku Basic --admin-enabled true | Out-Null

Write-Host "[3/5] Ensuring Azure Container Apps prerequisites..."
az extension add --name containerapp --upgrade | Out-Null
az provider register --namespace Microsoft.App | Out-Null
az provider register --namespace Microsoft.OperationalInsights | Out-Null

Write-Host "[4/5] Creating ACA environment (if not exists)..."
az containerapp env create --name $ContainerAppEnv --resource-group $ResourceGroup --location $Location | Out-Null

Write-Host "[5/5] Building image and deploying Container App..."
$Image = "$AcrName.azurecr.io/researchhub-backend:$ImageTag"
az acr build --registry $AcrName --image "researchhub-backend:$ImageTag" --file backend/Dockerfile backend | Out-Null

az containerapp up `
    --name $ContainerAppName `
    --resource-group $ResourceGroup `
    --environment $ContainerAppEnv `
    --ingress external `
    --target-port 8000 `
    --registry-server "$AcrName.azurecr.io" `
    --image $Image | Out-Null

$Fqdn = az containerapp show --name $ContainerAppName --resource-group $ResourceGroup --query properties.configuration.ingress.fqdn -o tsv
$Url = "https://$Fqdn"

Write-Host "Deployment complete."
Write-Host "Backend URL: $Url"
Write-Host "Next: set backend env vars/secrets in Container App and update Vercel VITE_API_URL/VITE_API_BASE."
