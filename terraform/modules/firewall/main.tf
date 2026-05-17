# Allow SSH only via Google IAP
resource "google_compute_firewall" "allow_iap_ssh" {
  name    = "metrics-allow-iap-ssh"
  network = var.network
  project = var.project

  allow {
    protocol = "tcp"
    ports    = ["22"]
  }

  # Google IAP IP range
  source_ranges = ["35.235.240.0/20"]
  target_tags   = ["metrics-backend", "metrics-services", "metrics-mongodb"]

  description = "Allow SSH via Google Identity-Aware Proxy"
}

# Allow metrics API and Parquet download endpoint from the internet
resource "google_compute_firewall" "allow_metrics_api" {
  name    = "metrics-allow-api"
  network = var.network
  project = var.project

  allow {
    protocol = "tcp"
    ports    = ["8000"]
  }

  source_ranges = ["0.0.0.0/0"]
  target_tags   = ["metrics-backend"]

  description = "Allow FastAPI backend (metrics POST + Parquet downloads)"
}

# Allow Airflow UI access from admin IP only
resource "google_compute_firewall" "allow_airflow_ui" {
  name    = "metrics-allow-airflow"
  network = var.network
  project = var.project

  allow {
    protocol = "tcp"
    ports    = ["8080"]
  }

  source_ranges = [var.admin_cidr]
  target_tags   = ["metrics-services"]

  description = "Allow Airflow web UI from admin IP"
}

# Allow JupyterLab access from admin IP only
resource "google_compute_firewall" "allow_jupyter" {
  name    = "metrics-allow-jupyter"
  network = var.network
  project = var.project

  allow {
    protocol = "tcp"
    ports    = ["8888"]
  }

  source_ranges = [var.admin_cidr]
  target_tags   = ["metrics-services"]

  description = "Allow JupyterLab from admin IP"
}

# Allow MongoDB port — internal VPC only (never exposed to internet)
resource "google_compute_firewall" "allow_mongodb" {
  name    = "metrics-allow-mongodb"
  network = var.network
  project = var.project

  allow {
    protocol = "tcp"
    ports    = ["27017"]
  }

  source_ranges = ["10.0.1.0/24"]
  target_tags   = ["metrics-mongodb"]

  description = "Allow MongoDB from internal VPC only — no public access"
}

# Allow internal VPC traffic between VMs
resource "google_compute_firewall" "allow_internal" {
  name    = "metrics-allow-internal"
  network = var.network
  project = var.project

  allow {
    protocol = "tcp"
  }

  allow {
    protocol = "icmp"
  }

  source_ranges = ["10.0.1.0/24"]
  description   = "Allow all internal VPC traffic"
}
