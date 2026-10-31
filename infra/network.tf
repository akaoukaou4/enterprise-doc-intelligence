# We use the account's default VPC. No new network (D-55: no new AWS services).
data "aws_vpc" "default" {
  default = true
}

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}

# Server group: NO inbound rule at all (I17, D-56). Access is through SSM only.
resource "aws_security_group" "server" {
  name        = "enterprise-doc-ec2-sg"
  description = "Server: no inbound, outbound only"
  vpc_id      = data.aws_vpc.default.id
}

# Terraform deletes the default allow-all outbound rule, so it is declared here.
# The server needs outbound for Gemini, package downloads and the SSM agent.
resource "aws_vpc_security_group_egress_rule" "server_all_out" {
  security_group_id = aws_security_group.server.id
  ip_protocol       = "-1"
  cidr_ipv4         = "0.0.0.0/0"
}

# Database group: PostgreSQL only from the server group. No outbound needed.
resource "aws_security_group" "database" {
  name        = "enterprise-doc-rds-sg"
  description = "Database: PostgreSQL from the server group only"
  vpc_id      = data.aws_vpc.default.id
}

resource "aws_vpc_security_group_ingress_rule" "database_from_server" {
  security_group_id            = aws_security_group.database.id
  referenced_security_group_id = aws_security_group.server.id
  ip_protocol                  = "tcp"
  from_port                    = 5432
  to_port                      = 5432
}
