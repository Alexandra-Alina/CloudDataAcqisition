variable "project_id" {
  description = "GCP Project ID"
  type        = string
}

variable "region" {
  description = "GCP region (us-central1 for free tier eligibility)"
  type        = string
  default     = "us-central1"
}

variable "zone" {
  description = "GCP zone"
  type        = string
  default     = "us-central1-a"
}

variable "admin_cidr" {
  description = "Your IP CIDR block for accessing Airflow UI and JupyterLab (e.g. 1.2.3.4/32)"
  type        = string
}

variable "backend_vm_machine_type" {
  description = "Machine type for the backend VM (e2-micro is free tier eligible)"
  type        = string
  default     = "e2-micro"
}

variable "services_vm_machine_type" {
  description = "Machine type for the services VM (Airflow + JupyterLab)"
  type        = string
  default     = "e2-small"
}

variable "mongodb_vm_machine_type" {
  description = "Machine type for the MongoDB VM (e2-micro ~$6/mo)"
  type        = string
  default     = "e2-micro"
}

variable "repo_url" {
  description = "Git repository URL to clone on VMs at startup"
  type        = string
  default     = "https://github.com/CHANGE_ME/CloudDataAquisition.git"
}
