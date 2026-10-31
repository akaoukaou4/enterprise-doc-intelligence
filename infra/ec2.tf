# Latest Amazon Linux 2023 image, from the AWS public parameter.
data "aws_ssm_parameter" "al2023_ami" {
  name = "/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64"
}

resource "aws_instance" "server" {
  ami           = data.aws_ssm_parameter.al2023_ami.value
  instance_type = "m7i-flex.large" # 8 GiB, allowed on the Free plan (D-59)
  subnet_id     = sort(data.aws_subnets.default.ids)[0]

  vpc_security_group_ids = [aws_security_group.server.id]
  iam_instance_profile   = aws_iam_instance_profile.server.name

  # Outbound only: no inbound rule exists (I17). No key pair: access is SSM.
  associate_public_ip_address = true

  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required" # IMDSv2 only
    http_put_response_hop_limit = 2          # containers need it for the role (D-58)
  }

  root_block_device {
    volume_size = 50
    volume_type = "gp3"
  }

  user_data = file("${path.module}/user_data.sh")

  tags = {
    Name = "enterprise-doc-server"
  }

  lifecycle {
    # A newer image must not replace the server on a later plan.
    ignore_changes = [ami]
  }
}
