variable "project" {
  type = string
}

variable "zone" {
  type = string
}

variable "machine_type" {
  type    = string
  default = "e2-micro"
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
