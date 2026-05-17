output "iap_ssh_rule" {
  value = google_compute_firewall.allow_iap_ssh.name
}

output "api_rule" {
  value = google_compute_firewall.allow_metrics_api.name
}
