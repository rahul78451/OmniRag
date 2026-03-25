terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
  required_version = ">= 1.3.0"
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# ─────────────────────────────────────────────
# Enable required APIs
# ─────────────────────────────────────────────
resource "google_project_service" "apis" {
  for_each = toset([
    "run.googleapis.com",
    "aiplatform.googleapis.com",
    "storage.googleapis.com",
    "firestore.googleapis.com",
    "cloudbuild.googleapis.com",
    "containerregistry.googleapis.com",
    "iam.googleapis.com",
  ])
  service            = each.key
  disable_on_destroy = false
}

# ─────────────────────────────────────────────
# Cloud Storage bucket for documents
# ─────────────────────────────────────────────
resource "google_storage_bucket" "docs" {
  name          = "${var.project_id}-omnirag-docs"
  location      = "US"
  force_destroy = true

  uniform_bucket_level_access = true

  lifecycle_rule {
    condition { age = 365 }
    action    { type = "Delete" }
  }

  depends_on = [google_project_service.apis]
}

# ─────────────────────────────────────────────
# Firestore database
# ─────────────────────────────────────────────
resource "google_firestore_database" "sessions" {
  name        = "(default)"
  location_id = var.region
  type        = "FIRESTORE_NATIVE"

  depends_on = [google_project_service.apis]
}

# ─────────────────────────────────────────────
# Service account for Cloud Run
# ─────────────────────────────────────────────
resource "google_service_account" "omnirag_sa" {
  account_id   = "omnirag-backend-sa"
  display_name = "OmniRAG Backend Service Account"
}

resource "google_project_iam_member" "sa_roles" {
  for_each = toset([
    "roles/aiplatform.user",
    "roles/datastore.user",
    "roles/storage.objectAdmin",
    "roles/logging.logWriter",
  ])
  project = var.project_id
  role    = each.key
  member  = "serviceAccount:${google_service_account.omnirag_sa.email}"
}

# ─────────────────────────────────────────────
# Cloud Run backend
# ─────────────────────────────────────────────
resource "google_cloud_run_v2_service" "backend" {
  name     = "omnirag-backend"
  location = var.region

  template {
    service_account = google_service_account.omnirag_sa.email

    containers {
      image = "gcr.io/${var.project_id}/omnirag-backend:latest"

      ports {
        container_port = 8080
      }

      env {
        name  = "PROJECT_ID"
        value = var.project_id
      }
      env {
        name  = "LOCATION"
        value = var.region
      }
      env {
        name  = "GCS_BUCKET"
        value = google_storage_bucket.docs.name
      }

      resources {
        limits = {
          cpu    = "2"
          memory = "2Gi"
        }
      }
    }

    scaling {
      min_instance_count = 0
      max_instance_count = 10
    }
  }

  depends_on = [
    google_project_service.apis,
    google_project_iam_member.sa_roles,
  ]
}

# ─────────────────────────────────────────────
# Allow public access to Cloud Run
# ─────────────────────────────────────────────
resource "google_cloud_run_v2_service_iam_member" "public_access" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.backend.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# ─────────────────────────────────────────────
# Cloud Run frontend
# ─────────────────────────────────────────────
resource "google_cloud_run_v2_service" "frontend" {
  name     = "omnirag-frontend"
  location = var.region

  template {
    containers {
      image = "gcr.io/${var.project_id}/omnirag-frontend:latest"

      ports {
        container_port = 3000
      }

      env {
        name  = "NEXT_PUBLIC_BACKEND_URL"
        value = google_cloud_run_v2_service.backend.uri
      }
    }
  }

  depends_on = [google_project_service.apis]
}

resource "google_cloud_run_v2_service_iam_member" "frontend_public" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.frontend.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# ─────────────────────────────────────────────
# Outputs
# ─────────────────────────────────────────────
output "backend_url" {
  value       = google_cloud_run_v2_service.backend.uri
  description = "Backend Cloud Run URL"
}

output "frontend_url" {
  value       = google_cloud_run_v2_service.frontend.uri
  description = "Frontend Cloud Run URL"
}

output "gcs_bucket" {
  value       = google_storage_bucket.docs.name
  description = "GCS bucket for documents"
}
