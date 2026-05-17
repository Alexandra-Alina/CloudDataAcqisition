resource "google_compute_address" "services_ip" {
  name    = "metrics-services-ip"
  region  = replace(var.zone, "/-[a-z]$/", "")
  project = var.project
}

resource "google_compute_instance" "services_vm" {
  name         = "metrics-services-vm"
  machine_type = var.machine_type
  zone         = var.zone
  project      = var.project

  tags = ["metrics-services"]

  boot_disk {
    initialize_params {
      image = "ubuntu-os-cloud/ubuntu-2204-lts"
      size  = 30
      type  = "pd-standard"
    }
  }

  network_interface {
    subnetwork = var.subnet

    access_config {
      nat_ip = google_compute_address.services_ip.address
    }
  }

  service_account {
    email  = var.service_account_email
    scopes = ["cloud-platform"]
  }

  metadata_startup_script = templatefile("${path.module}/startup.sh", {
    REPO_URL        = var.repo_url
    GCS_BUCKET_NAME = var.gcs_bucket_name
  })

  shielded_instance_config {
    enable_secure_boot          = true
    enable_vtpm                 = true
    enable_integrity_monitoring = true
  }

  labels = {
    component = "services"
    managed   = "terraform"
  }
}
