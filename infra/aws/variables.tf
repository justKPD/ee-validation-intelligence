variable "region" {
  type    = string
  default = "eu-central-1"
}

variable "project" {
  type    = string
  default = "ee-validation"
}

variable "image_tag" {
  type    = string
  default = "latest"
}

variable "db_instance_class" {
  type    = string
  default = "db.t4g.micro"
}

variable "model_provider" {
  description = "offline (default, deterministic) or anthropic"
  type        = string
  default     = "offline"
}
