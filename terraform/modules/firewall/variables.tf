variable "project" {
  description = "GCP Project ID"
  type        = string
}

variable "network" {
  description = "VPC network name"
  type        = string
}

variable "admin_cidr" {
  description = "Admin IP CIDR for Airflow UI and JupyterLab access"
  type        = string
}
