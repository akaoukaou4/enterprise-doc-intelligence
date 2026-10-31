variable "region" {
  description = "AWS region. Same as the manual build (D-55)."
  type        = string
  default     = "eu-north-1"
}

variable "rds_password" {
  description = "Master password of the database. Set with TF_VAR_rds_password, never in a file."
  type        = string
  sensitive   = true

  # Letters and digits only: symbols break the DATABASE_URL (D-58).
  validation {
    condition     = can(regex("^[A-Za-z0-9]{12,}$", var.rds_password))
    error_message = "Use at least 12 characters, letters and digits only."
  }
}

variable "budget_email" {
  description = "Email for budget alerts. Set with TF_VAR_budget_email, never in a file."
  type        = string
  sensitive   = true
}
