# No db_subnet_group_name: RDS uses the default subnet group of the default VPC,
# the same as the manual build.
resource "aws_db_instance" "main" {
  identifier = "enterprise-doc-db"

  engine         = "postgres"
  engine_version = "18.3"
  instance_class = "db.t4g.micro"

  allocated_storage = 20
  storage_type      = "gp3"
  storage_encrypted = true

  db_name  = "enterprise_docs"
  username = "appadmin"
  password = var.rds_password

  vpc_security_group_ids = [aws_security_group.database.id]
  publicly_accessible    = false # I17
  multi_az               = false

  backup_retention_period = 1
  deletion_protection     = false
  apply_immediately       = true

  # Lets "terraform destroy" remove everything. Safe: fictional corpus only.
  skip_final_snapshot = true
}
