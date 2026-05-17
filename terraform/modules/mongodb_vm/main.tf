# MongoDB VM — no external IP (internal VPC only, reachable via Cloud NAT for outbound)
resource "google_compute_instance" "mongodb_vm" {
  name         = "metrics-mongodb-vm"
  machine_type = var.machine_type
  zone         = var.zone
  project      = var.project

  tags = ["metrics-mongodb"]

  boot_disk {
    initialize_params {
      image = "ubuntu-os-cloud/ubuntu-2204-lts"
      size  = 20
      type  = "pd-standard"
    }
  }

  network_interface {
    subnetwork = var.subnet
    # No access_config block = no external IP (internal VPC only)
  }

  service_account {
    email  = var.service_account_email
    scopes = ["cloud-platform"]
  }

  metadata_startup_script = file("${path.module}/startup.sh")

  shielded_instance_config {
    enable_secure_boot          = true
    enable_vtpm                 = true
    enable_integrity_monitoring = true
  }

  labels = {
    component = "mongodb"
    managed   = "terraform"
  }
}
