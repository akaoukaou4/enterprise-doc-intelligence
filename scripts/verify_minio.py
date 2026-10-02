import boto3
from botocore.client import Config

ENDPOINT = "http://localhost:9000"
ACCESS_KEY = "minioadmin"  # pragma: allowlist secret
SECRET_KEY = "minioadmin123"  # pragma: allowlist secret
BUCKET = "documents"
OBJECT_KEY = "verification/test.txt"

TEST_CONTENT = b"Enterprise Document Intelligence - MinIO S3 verification."


def main() -> None:
    s3 = boto3.client(
        "s3",
        endpoint_url=ENDPOINT,
        aws_access_key_id=ACCESS_KEY,
        aws_secret_access_key=SECRET_KEY,
        region_name="us-east-1",
        config=Config(s3={"addressing_style": "path"}),
    )

    print("1. Connecting to MinIO...")
    response = s3.list_buckets()

    bucket_names = [bucket["Name"] for bucket in response["Buckets"]]

    if BUCKET not in bucket_names:
        raise RuntimeError(f"Bucket '{BUCKET}' was not found.")

    print(f"   OK: bucket '{BUCKET}' found.")

    print("2. Uploading test object...")
    s3.put_object(
        Bucket=BUCKET,
        Key=OBJECT_KEY,
        Body=TEST_CONTENT,
        ContentType="text/plain",
    )
    print("   OK: upload successful.")

    print("3. Downloading test object...")
    response = s3.get_object(
        Bucket=BUCKET,
        Key=OBJECT_KEY,
    )

    downloaded_content = response["Body"].read()

    if downloaded_content != TEST_CONTENT:
        raise RuntimeError("Downloaded content does not match uploaded content.")

    print("   OK: downloaded content matches.")

    print("4. Cleaning up test object...")
    s3.delete_object(
        Bucket=BUCKET,
        Key=OBJECT_KEY,
    )
    print("   OK: test object deleted.")

    print("\nMinIO boto3 verification PASSED.")


if __name__ == "__main__":
    main()
