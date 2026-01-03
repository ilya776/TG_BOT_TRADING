variable "project_id" {
  description = "GCP Project ID"
  type        = string
}

variable "region" {
  description = "GCP Region"
  type        = string
  default     = "europe-west4"
}

variable "zone" {
  description = "GCP Zone"
  type        = string
  default     = "europe-west4-a"
}

variable "vm_name" {
  description = "VM Instance Name"
  type        = string
  default     = "whale-bot-vm"
}

variable "machine_type" {
  description = "Machine Type"
  type        = string
  default     = "e2-medium"
}

variable "docker_compose_repo" {
  description = "GitHub Repo URL"
  type        = string
  default     = "https://github.com/illabilous/TG_BOT_TRADING.git"
}
