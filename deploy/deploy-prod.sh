#!/bin/bash
set -euo pipefail

PROJECT_ID="${GCP_PROJECT_ID:-travelhub-prod-492116}"
REGION="${GCP_REGION:-us-central1}"
SERVICE_NAME="notification-services"
IMAGE="us-central1-docker.pkg.dev/${PROJECT_ID}/travelhub/${SERVICE_NAME}:latest"

echo ">>> Building..."
gcloud builds submit --tag "${IMAGE}" --project "${PROJECT_ID}"

echo ">>> Deploying to Cloud Run (PROD)..."
gcloud run deploy "${SERVICE_NAME}" \
  --image "${IMAGE}" \
  --region "${REGION}" \
  --project "${PROJECT_ID}" \
  --network=travelhub-vpc \
  --subnet=subnet-services \
  --vpc-egress=private-ranges-only \
  --clear-vpc-connector \
  --port 8004 \
  --min-instances=1 \
  --max-instances=5 \
  --no-cpu-throttling \
  --set-env-vars "ENV=prod,KAFKA_CONSUMER_ENABLED=false,JWT_ISSUER=https://auth.travelhub.app,JWT_AUDIENCE=travelhub-api,APP_URL=https://app.travelhub.app,SUPPORT_EMAIL=soporte@travelhub.app,SENDGRID_FROM_EMAIL=noreply@travelhub.app,SENDGRID_FROM_NAME=TravelHub,SENDGRID_SANDBOX=false,FCM_PROJECT_ID=${PROJECT_ID}" \
  --set-secrets "DATABASE_URL=prod-travelhub-notification-db-url:latest,SENDGRID_API_KEY=prod-travelhub-sendgrid-api-key:latest,FCM_CREDENTIALS_JSON=prod-travelhub-fcm-credentials:latest,INTERNAL_NOTIFY_TOKEN=prod-travelhub-internal-notify-token:latest" \
  --service-account "github-deploy-notification@${PROJECT_ID}.iam.gserviceaccount.com" \
  --allow-unauthenticated

echo ">>> PROD deploy done."
