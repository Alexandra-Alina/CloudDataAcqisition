provider "google" {
  project = var.project_id
  region  = var.region
  zone    = var.zone
}

# ── Enable required APIs ──────────────────────────────────────────────────────

resource "google_project_service" "apis" {
  for_each = toset([
    "compute.googleapis.com",
    "secretmanager.googleapis.com",
    "storage.googleapis.com",
    "iam.googleapis.com",
    "cloudresourcemanager.googleapis.com",
    "iap.googleapis.com",
  ])

  project            = var.project_id
  service            = each.key
  disable_on_destroy = false
}

# ── Service Accounts ──────────────────────────────────────────────────────────

resource "google_service_account" "backend_sa" {
  account_id   = "metrics-backend-sa"
  display_name = "Metrics Backend VM Service Account"
  depends_on   = [google_project_service.apis]
}

resource "google_service_account" "services_sa" {
  account_id   = "metrics-services-sa"
  display_name = "Metrics Services VM Service Account"
  depends_on   = [google_project_service.apis]
}

# IAM bindings for backend SA
resource "google_project_iam_member" "backend_secret_accessor" {
  project = var.project_id
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${google_service_account.backend_sa.email}"
}

resource "google_project_iam_member" "backend_log_writer" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.backend_sa.email}"
}

resource "google_project_iam_member" "backend_metric_writer" {
  project = var.project_id
  role    = "roles/monitoring.metricWriter"
  member  = "serviceAccount:${google_service_account.backend_sa.email}"
}

# IAM bindings for services SA
resource "google_project_iam_member" "services_storage_admin" {
  project = var.project_id
  role    = "roles/storage.objectAdmin"
  member  = "serviceAccount:${google_service_account.services_sa.email}"
}

resource "google_project_iam_member" "services_secret_accessor" {
  project = var.project_id
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${google_service_account.services_sa.email}"
}

resource "google_project_iam_member" "services_log_writer" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.services_sa.email}"
}

# ── Service Account for MongoDB VM ───────────────────────────────────────────

resource "google_service_account" "mongodb_sa" {
  account_id   = "metrics-mongodb-sa"
  display_name = "Metrics MongoDB VM Service Account"
  depends_on   = [google_project_service.apis]
}

resource "google_project_iam_member" "mongodb_secret_accessor" {
  project = var.project_id
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${google_service_account.mongodb_sa.email}"
}

resource "google_project_iam_member" "mongodb_log_writer" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.mongodb_sa.email}"
}

# ── Secret Manager ────────────────────────────────────────────────────────────
# Secrets are placeholders — values are set manually via gcloud after terraform apply

resource "google_secret_manager_secret" "mongodb_uri" {
  secret_id = "mongodb-uri"
  replication {
    auto {}
  }
  depends_on = [google_project_service.apis]
}

resource "google_secret_manager_secret" "mongodb_username" {
  secret_id = "mongodb-username"
  replication {
    auto {}
  }
  depends_on = [google_project_service.apis]
}

resource "google_secret_manager_secret" "mongodb_password" {
  secret_id = "mongodb-password"
  replication {
    auto {}
  }
  depends_on = [google_project_service.apis]
}

resource "google_secret_manager_secret" "backend_api_key" {
  secret_id = "backend-api-key"
  replication {
    auto {}
  }
  depends_on = [google_project_service.apis]
}

# ── Modules ───────────────────────────────────────────────────────────────────

module "networking" {
  source  = "./modules/networking"
  project = var.project_id
  region  = var.region
}

module "firewall" {
  source     = "./modules/firewall"
  project    = var.project_id
  network    = module.networking.network_name
  admin_cidr = var.admin_cidr
}

module "storage" {
  source      = "./modules/storage"
  project     = var.project_id
  region      = var.region
  services_sa = google_service_account.services_sa.email
}

module "backend_vm" {
  source       = "./modules/backend_vm"
  project      = var.project_id
  zone         = var.zone
  machine_type = var.backend_vm_machine_type
  subnet       = module.networking.subnet_self_link
  service_account_email = google_service_account.backend_sa.email
  repo_url     = var.repo_url
}

module "services_vm" {
  source                = "./modules/services_vm"
  project               = var.project_id
  zone                  = var.zone
  machine_type          = var.services_vm_machine_type
  subnet                = module.networking.subnet_self_link
  service_account_email = google_service_account.services_sa.email
  repo_url              = var.repo_url
  gcs_bucket_name       = module.storage.bucket_name
}

module "mongodb_vm" {
  source                = "./modules/mongodb_vm"
  project               = var.project_id
  zone                  = var.zone
  machine_type          = var.mongodb_vm_machine_type
  subnet                = module.networking.subnet_self_link
  service_account_email = google_service_account.mongodb_sa.email
}
