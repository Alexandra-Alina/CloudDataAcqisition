variable "project" {
  description = "GCP Project ID"
  type        = string
}

variable "region" {
  description = "GCP region"
  type        = string
}

variable "services_sa" {
  description = "Services VM service account email"
  type        = string
}
