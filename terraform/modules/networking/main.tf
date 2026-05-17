resource "google_compute_network" "vpc" {
  name                    = "metrics-vpc"
  auto_create_subnetworks = false
  project                 = var.project
}

resource "google_compute_subnetwork" "subnet" {
  name          = "metrics-subnet"
  ip_cidr_range = "10.0.1.0/24"
  region        = var.region
  network       = google_compute_network.vpc.id
  project       = var.project

  private_ip_google_access = true
}

resource "google_compute_router" "router" {
  name    = "metrics-router"
  region  = var.region
  network = google_compute_network.vpc.id
  project = var.project
}

resource "google_compute_router_nat" "nat" {
  name                               = "metrics-nat"
  router                             = google_compute_router.router.name
  region                             = var.region
  project                            = var.project
  nat_ip_allocate_option             = "AUTO_ONLY"
  source_subnetwork_ip_ranges_to_nat = "ALL_SUBNETWORKS_ALL_IP_RANGES"

  log_config {
    enable = false
    filter = "ERRORS_ONLY"
  }
}
