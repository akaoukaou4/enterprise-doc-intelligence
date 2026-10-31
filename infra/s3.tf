resource "aws_s3_bucket" "documents" {
  bucket = "enterprise-doc-intel-483920"

  # Lets "terraform destroy" delete a non-empty bucket. Safe: only the fictional
  # corpus is stored here (D-36). Remove this before any real company data.
  force_destroy = true
}

resource "aws_s3_bucket_public_access_block" "documents" {
  bucket                  = aws_s3_bucket.documents.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
