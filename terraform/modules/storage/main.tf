resource "google_storage_bucket" "parquet_exports" {
  name          = "metrics-parquet-${var.project}"
  location      = var.region
  storage_class = "STANDARD"
  project       = var.project

  uniform_bucket_level_access = true

  lifecycle_rule {
    condition {
      age = 90
    }
    action {
      type = "Delete"
    }
  }

  # Prevent accidental public access
  public_access_prevention = "enforced"
}

resource "google_storage_bucket_iam_member" "services_sa_writer" {
  bucket = google_storage_bucket.parquet_exports.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${var.services_sa}"
}
