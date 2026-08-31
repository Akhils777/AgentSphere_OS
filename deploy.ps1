param(
  [Parameter(Mandatory=$true)][string]$ProjectId,
  [string]$Region = "us-central1"
)

$ErrorActionPreference = "Stop"
$Image = "$Region-docker.pkg.dev/$ProjectId/agentsphere/api:latest"
$ServiceAccount = "agentsphere-runtime@$ProjectId.iam.gserviceaccount.com"
$rendered = Join-Path $env:TEMP "agentsphere-cloudrun.yaml"

gcloud config set project $ProjectId
gcloud services enable run.googleapis.com artifactregistry.googleapis.com cloudbuild.googleapis.com firestore.googleapis.com aiplatform.googleapis.com
gcloud iam service-accounts describe $ServiceAccount 2>$null
if ($LASTEXITCODE -ne 0) {
  gcloud iam service-accounts create agentsphere-runtime --display-name="AgentSphere Cloud Run runtime"
}
gcloud projects add-iam-policy-binding $ProjectId --member="serviceAccount:$ServiceAccount" --role="roles/datastore.user"
gcloud projects add-iam-policy-binding $ProjectId --member="serviceAccount:$ServiceAccount" --role="roles/aiplatform.user"
gcloud builds submit --tag $Image .

$yaml = (Get-Content backend/cloudrun.yaml -Raw).Replace("PROJECT_ID", $ProjectId).Replace("REGION", $Region).Replace("IMAGE_PLACEHOLDER", $Image)
$yaml | Set-Content $rendered -Encoding utf8
gcloud run services replace $rendered --region $Region
gcloud run services add-iam-policy-binding agentsphere-api --region $Region --member="allUsers" --role="roles/run.invoker"
gcloud run services describe agentsphere-api --region $Region --format="value(status.url)"

