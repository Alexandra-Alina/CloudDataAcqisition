output "backend_vm_external_ip" {
  description = "External IP of the FastAPI backend VM"
  value       = module.backend_vm.external_ip
}

output "services_vm_external_ip" {
  description = "External IP of the services VM (Airflow + JupyterLab)"
  value       = module.services_vm.external_ip
}

output "gcs_bucket_name" {
  description = "GCS bucket for Parquet exports"
  value       = module.storage.bucket_name
}

output "backend_sa_email" {
  description = "Backend VM service account email"
  value       = google_service_account.backend_sa.email
}

output "services_sa_email" {
  description = "Services VM service account email"
  value       = google_service_account.services_sa.email
}

output "airflow_ui_url" {
  description = "Airflow web UI URL"
  value       = "http://${module.services_vm.external_ip}:8080"
}

output "jupyter_url" {
  description = "JupyterLab URL"
  value       = "http://${module.services_vm.external_ip}:8888"
}

output "metrics_api_url" {
  description = "FastAPI backend base URL"
  value       = "http://${module.backend_vm.external_ip}:8000"
}

output "mongodb_internal_ip" {
  description = "Internal VPC IP of MongoDB VM — use in MONGODB_URI after terraform apply"
  value       = module.mongodb_vm.internal_ip
}

output "mongodb_uri_template" {
  description = "MongoDB connection URI template — replace PASSWORD with your secret value"
  value       = "mongodb://metrics_user:PASSWORD@${module.mongodb_vm.internal_ip}:27017/metrics_db?authSource=admin"
}

output "ssh_backend_vm" {
  description = "IAP SSH command for backend VM"
  value       = "gcloud compute ssh metrics-backend-vm --zone ${var.zone} --tunnel-through-iap"
}

output "ssh_services_vm" {
  description = "IAP SSH command for services VM"
  value       = "gcloud compute ssh metrics-services-vm --zone ${var.zone} --tunnel-through-iap"
}

output "ssh_mongodb_vm" {
  description = "IAP SSH command for MongoDB VM"
  value       = "gcloud compute ssh metrics-mongodb-vm --zone ${var.zone} --tunnel-through-iap"
}
