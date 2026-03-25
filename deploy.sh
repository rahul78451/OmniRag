#!/usr/bin/env bash
# OmniRAG — One-click GCP deployment script
# Usage: ./deploy.sh <YOUR_GCP_PROJECT_ID>

set -euo pipefail

PROJECT_ID="${1:-omnirag-agent}"
REGION="us-central1"

echo "======================================"
echo "  OmniRAG Deployment Script"
echo "  Project: $PROJECT_ID"
echo "======================================"

# 1. Set project
gcloud config set project "$PROJECT_ID"

# 2. Enable APIs
echo "[1/6] Enabling Google Cloud APIs..."
gcloud services enable \
  run.googleapis.com \
  aiplatform.googleapis.com \
  storage.googleapis.com \
  firestore.googleapis.com \
  cloudbuild.googleapis.com \
  containerregistry.googleapis.com

# 3. Create GCS bucket
echo "[2/6] Creating Cloud Storage bucket..."
BUCKET="${PROJECT_ID}-omnirag-docs"
gsutil mb -l US "gs://$BUCKET" 2>/dev/null || echo "Bucket already exists"

# 4. Build & push backend
echo "[3/6] Building backend Docker image..."
gcloud builds submit \
  --tag "gcr.io/$PROJECT_ID/omnirag-backend:latest" \
  --dockerfile Dockerfile \
  .

# 5. Deploy backend to Cloud Run
echo "[4/6] Deploying backend to Cloud Run..."
gcloud run deploy omnirag-backend \
  --image "gcr.io/$PROJECT_ID/omnirag-backend:latest" \
  --region "$REGION" \
  --platform managed \
  --allow-unauthenticated \
  --memory 2Gi \
  --cpu 2 \
  --set-env-vars "PROJECT_ID=$PROJECT_ID,LOCATION=$REGION,GCS_BUCKET=$BUCKET"

# 6. Get backend URL and build frontend
BACKEND_URL=$(gcloud run services describe omnirag-backend \
  --region "$REGION" \
  --format "value(status.url)")

echo "[5/6] Building frontend Docker image..."
gcloud builds submit \
  --tag "gcr.io/$PROJECT_ID/omnirag-frontend:latest" \
  --dockerfile frontend/Dockerfile \
  ./frontend \
  --substitutions "_BACKEND_URL=$BACKEND_URL"

# 7. Deploy frontend
echo "[6/6] Deploying frontend to Cloud Run..."
gcloud run deploy omnirag-frontend \
  --image "gcr.io/$PROJECT_ID/omnirag-frontend:latest" \
  --region "$REGION" \
  --platform managed \
  --allow-unauthenticated \
  --set-env-vars "NEXT_PUBLIC_BACKEND_URL=$BACKEND_URL"

FRONTEND_URL=$(gcloud run services describe omnirag-frontend \
  --region "$REGION" \
  --format "value(status.url)")

echo ""
echo "======================================"
echo "  Deployment complete!"
echo "  Backend:  $BACKEND_URL"
echo "  Frontend: $FRONTEND_URL"
echo "======================================"
