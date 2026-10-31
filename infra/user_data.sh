#!/bin/bash
# Base setup only (D-61). The clone, .env and image build stay manual (D-57):
# secrets must not enter Terraform code or state.
set -euxo pipefail

# Swap file for the memory peaks of one ingestion (D-59).
fallocate -l 4G /swapfile
chmod 600 /swapfile
mkswap /swapfile
swapon /swapfile
echo '/swapfile none swap sw 0 0' >> /etc/fstab

dnf install -y docker git
systemctl enable --now docker

# Compose and Buildx plugins, versions as installed by hand in Phase 12 (E-7).
mkdir -p /usr/local/lib/docker/cli-plugins
curl -fSL -o /usr/local/lib/docker/cli-plugins/docker-compose \
  https://github.com/docker/compose/releases/download/v5.6.1/docker-compose-linux-x86_64
curl -fSL -o /usr/local/lib/docker/cli-plugins/docker-buildx \
  https://github.com/docker/buildx/releases/download/v0.38.1/buildx-v0.38.1.linux-amd64
chmod +x /usr/local/lib/docker/cli-plugins/docker-compose /usr/local/lib/docker/cli-plugins/docker-buildx
