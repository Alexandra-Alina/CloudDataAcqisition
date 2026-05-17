output "external_ip" {
  value = google_compute_address.backend_ip.address
}

output "instance_name" {
  value = google_compute_instance.backend_vm.name
}
