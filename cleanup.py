"""
AWS S3 + CloudFront Demo — CLEANUP
===================================
Run this after the demo to delete all created AWS resources
and avoid ongoing charges.

Usage:
  python cleanup.py <BUCKET_NAME> <DISTRIBUTION_ID>

Example:
  python cleanup.py demo-s3-cf-a1b2c3d4 E1A2B3C4D5EXMP
"""

import boto3
import sys
import time

if len(sys.argv) != 3:
    print(__doc__)
    sys.exit(1)

BUCKET_NAME = sys.argv[1]
DIST_ID     = sys.argv[2]
REGION      = "eu-central-1"   # must match what you used in demo.py

s3 = boto3.client("s3", region_name=REGION)
cf = boto3.client("cloudfront", region_name="us-east-1")

print(f"\nCleaning up resources...")
print(f"  Bucket:       {BUCKET_NAME}")
print(f"  Distribution: {DIST_ID}\n")

# ── 1. Disable CloudFront distribution ───────────────────────────────────────
print("Step 1: Disabling CloudFront distribution...")
dist = cf.get_distribution(Id=DIST_ID)
etag = dist["ETag"]
config = dist["Distribution"]["DistributionConfig"]
config["Enabled"] = False

cf.update_distribution(
    Id=DIST_ID,
    IfMatch=etag,
    DistributionConfig=config,
)
print("  ✓ Distribution disabled — waiting for it to deploy (this takes ~5 min)...")

for i in range(60):
    status = cf.get_distribution(Id=DIST_ID)["Distribution"]["Status"]
    print(f"  ... Status: {status} ({i*10}s)", end="\r")
    if status == "Deployed":
        print(f"\n  ✓ Distribution disabled and deployed")
        break
    time.sleep(10)

# ── 2. Delete CloudFront distribution ────────────────────────────────────────
print("\nStep 2: Deleting CloudFront distribution...")
dist = cf.get_distribution(Id=DIST_ID)
etag = dist["ETag"]
cf.delete_distribution(Id=DIST_ID, IfMatch=etag)
print("  ✓ Distribution deleted")

# ── 3. Empty S3 bucket (delete all object versions) ──────────────────────────
print("\nStep 3: Emptying S3 bucket (all versions)...")
paginator = s3.get_paginator("list_object_versions")
for page in paginator.paginate(Bucket=BUCKET_NAME):
    objects = []
    for v in page.get("Versions", []):
        objects.append({"Key": v["Key"], "VersionId": v["VersionId"]})
    for m in page.get("DeleteMarkers", []):
        objects.append({"Key": m["Key"], "VersionId": m["VersionId"]})
    if objects:
        s3.delete_objects(Bucket=BUCKET_NAME, Delete={"Objects": objects})
        print(f"  ✓ Deleted {len(objects)} object version(s)")

# ── 4. Delete S3 bucket ───────────────────────────────────────────────────────
print("\nStep 4: Deleting S3 bucket...")
s3.delete_bucket(Bucket=BUCKET_NAME)
print(f"  ✓ Bucket {BUCKET_NAME} deleted")

print("\n✅ Cleanup complete. No ongoing charges.\n")
