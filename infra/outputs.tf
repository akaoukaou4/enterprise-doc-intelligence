output "instance_id" {
  description = "Target of the SSM tunnel and of the Session Manager shell."
  value       = aws_instance.server.id
}

output "rds_host" {
  description = "Value of RDS_HOST in the server's .env."
  value       = aws_db_instance.main.address
}

output "bucket" {
  value = aws_s3_bucket.documents.bucket
}
