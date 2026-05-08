#!/bin/bash
# setup-wif-dev.sh
# Idempotent: creates SA, grants roles, and wires WIF for notification-services DEV deploy.
# Run once with: bash scripts/setup-wif-dev.sh
set -euo pipefail

PROJECT_ID="gen-lang-client-0930444414"
PROJECT_NUMBER="154299161799"
REGION="us-central1"
SA_NAME="github-deploy-notification"
SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
WIF_POOL="github-pool"
WIF_PROVIDER="github-provider"
GH_REPO="ecruzs-uniandes/miso-travelhub-notification-services"

echo "=== [1/5] Ensuring SA exists ==="
if gcloud iam service-accounts describe "${SA_EMAIL}" --project="${PROJECT_ID}" &>/dev/null; then
  echo "  SA already exists: ${SA_EMAIL}"
else
  gcloud iam service-accounts create "${SA_NAME}" \
    --project="${PROJECT_ID}" \
    --display-name="GitHub Deploy - notification-services"
  echo "  Created: ${SA_EMAIL}"
fi

echo ""
echo "=== [2/5] Granting IAM roles to SA ==="
for ROLE in \
  roles/run.admin \
  roles/iam.serviceAccountUser \
  roles/artifactregistry.writer \
  roles/secretmanager.secretAccessor; do
  echo "  Binding ${ROLE}..."
  gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="${ROLE}" \
    --condition=None \
    --quiet
done

echo ""
echo "=== [3/5] Reading current WIF provider attribute condition ==="
CURRENT_CONDITION=$(gcloud iam workload-identity-pools providers describe "${WIF_PROVIDER}" \
  --workload-identity-pool="${WIF_POOL}" \
  --location=global \
  --project="${PROJECT_ID}" \
  --format="value(attributeCondition)" 2>/dev/null || echo "")

echo "  Current condition: ${CURRENT_CONDITION:-'(none)'}"

echo ""
echo "=== [4/5] Updating WIF provider attribute condition ==="
# Check if the repo is already in the condition
if echo "${CURRENT_CONDITION}" | grep -q "${GH_REPO}"; then
  echo "  Repo already in condition — skipping update."
else
  # Build the new condition by appending this repo.
  # We replace owner-based conditions too; safest is to check type first.
  if echo "${CURRENT_CONDITION}" | grep -q "repository_owner"; then
    echo "  Provider uses repository_owner condition — no update needed (all repos in org are allowed)."
  else
    # Extract existing repos from the condition string and add the new one.
    # Condition format: attribute.repository in ["repo1", "repo2", ...]
    NEW_CONDITION="attribute.repository in [\"ecruzs-uniandes/miso-travelhub-user-services\", \"ecruzs-uniandes/miso-travelhub-pms-intergration-services\", \"ecruzs-uniandes/miso-travelhub-pms-sync-worker\", \"${GH_REPO}\"]"
    echo "  Applying new condition: ${NEW_CONDITION}"
    gcloud iam workload-identity-pools providers update-oidc "${WIF_PROVIDER}" \
      --workload-identity-pool="${WIF_POOL}" \
      --location=global \
      --project="${PROJECT_ID}" \
      --attribute-condition="${NEW_CONDITION}"
    echo "  Done."
  fi
fi

echo ""
echo "=== [5/5] Binding SA to WIF principal for this repo ==="
WIF_PRINCIPAL="principalSet://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${WIF_POOL}/attribute.repository/${GH_REPO}"
echo "  Principal: ${WIF_PRINCIPAL}"
gcloud iam service-accounts add-iam-policy-binding "${SA_EMAIL}" \
  --project="${PROJECT_ID}" \
  --role=roles/iam.workloadIdentityUser \
  --member="${WIF_PRINCIPAL}" \
  --condition=None \
  --quiet
echo "  Bound."

echo ""
echo "=== All done ==="
echo "Re-run the GitHub Actions pipeline on branch feature/base-1 to verify deploy."
