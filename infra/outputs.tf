output "instance_ip" {
  value = google_compute_instance.vm_instance.network_interface[0].access_config[0].nat_ip
}

output "ssh_command" {
  value = "ssh -i ~/.ssh/id_rsa ${google_compute_instance.vm_instance.name}.${var.zone}.${var.project_id}"
}
