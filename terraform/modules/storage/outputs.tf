output "bucket_name" {
  value = google_storage_bucket.parquet_exports.name
}

output "bucket_url" {
  value = "gs://${google_storage_bucket.parquet_exports.name}"
}
