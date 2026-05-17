output "external_ip" {
  value = google_compute_address.services_ip.address
}

output "instance_name" {
  value = google_compute_instance.services_vm.name
}
