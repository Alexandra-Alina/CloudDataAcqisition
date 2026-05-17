variable "project" {
  type = string
}

variable "zone" {
  type = string
}

variable "machine_type" {
  type    = string
  default = "e2-small"
}

variable "subnet" {
  type = string
}

variable "service_account_email" {
  type = string
}

variable "repo_url" {
  type = string
}

variable "gcs_bucket_name" {
  description = "GCS bucket name for Parquet exports (passed to startup script via templatefile)"
  type        = string
}
