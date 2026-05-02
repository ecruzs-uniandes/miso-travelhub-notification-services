#!/bin/bash
set -euo pipefail

PROJECT_ID="${GCP_PROJECT_ID:-gen-lang-client-0930444414}"
REGION="${GCP_REGION:-us-central1}"
SERVICE_NAME="notification-services"
IMAGE="us-central1-docker.pkg.dev/${PROJECT_ID}/travelhub/${SERVICE_NAME}:latest"

echo ">>> Building..."
gcloud builds submit --tag "${IMAGE}" --project "${PROJECT_ID}"

echo ">>> Deploying to Cloud Run..."
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
  --max-instances=3 \
  --no-cpu-throttling \
  --set-env-vars "ENV=dev,KAFKA_CONSUMER_ENABLED=true,KAFKA_BOOTSTRAP_SERVERS=10.10.3.3:9092,JWT_ISSUER=https://auth.travelhub.app,JWT_AUDIENCE=travelhub-api,APP_URL=https://app.travelhub.app,SUPPORT_EMAIL=soporte@travelhub.app,SENDGRID_FROM_EMAIL=noreply@travelhub.app,SENDGRID_FROM_NAME=TravelHub,SENDGRID_SANDBOX=true,FCM_PROJECT_ID=${PROJECT_ID}" \
  --set-secrets "DATABASE_URL=dev-travelhub-notification-db-url:latest,SENDGRID_API_KEY=dev-travelhub-sendgrid-api-key:latest,FCM_CREDENTIALS_JSON=dev-travelhub-fcm-credentials:latest,INTERNAL_NOTIFY_TOKEN=dev-travelhub-internal-notify-token:latest" \
  --service-account "github-deploy-notification@${PROJECT_ID}.iam.gserviceaccount.com" \
  --allow-unauthenticated

echo ">>> Done. Recordar actualizar la URL en gateway/openapi-spec.yaml."
