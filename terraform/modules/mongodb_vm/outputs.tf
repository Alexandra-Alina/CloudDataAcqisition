output "internal_ip" {
  description = "Internal VPC IP of the MongoDB VM — use this in the MONGODB_URI"
  value       = google_compute_instance.mongodb_vm.network_interface[0].network_ip
}

output "instance_name" {
  value = google_compute_instance.mongodb_vm.name
}
