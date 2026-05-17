resource "google_compute_address" "backend_ip" {
  name    = "metrics-backend-ip"
  region  = replace(var.zone, "/-[a-z]$/", "")
  project = var.project
}

resource "google_compute_instance" "backend_vm" {
  name         = "metrics-backend-vm"
  machine_type = var.machine_type
  zone         = var.zone
  project      = var.project

  tags = ["metrics-backend"]

  boot_disk {
    initialize_params {
      image = "ubuntu-os-cloud/ubuntu-2204-lts"
      size  = 20
      type  = "pd-standard"
    }
  }

  network_interface {
    subnetwork = var.subnet

    access_config {
      nat_ip = google_compute_address.backend_ip.address
    }
  }

  service_account {
    email  = var.service_account_email
    scopes = ["cloud-platform"]
  }

  metadata_startup_script = templatefile("${path.module}/startup.sh", {
    REPO_URL = var.repo_url
  })

  shielded_instance_config {
    enable_secure_boot          = true
    enable_vtpm                 = true
    enable_integrity_monitoring = true
  }

  labels = {
    component = "backend"
    managed   = "terraform"
  }
}
