"""
AWS S3 + CloudFront Demo
========================
This script demonstrates the full workflow shown in the presentation:
  1. Create an S3 bucket with versioning
  2. Upload a static website (HTML + CSS)
  3. Attach an OAC-compatible bucket policy (blocks direct public access)
  4. Create a CloudFront distribution pointing to the S3 bucket
  5. Wait for the distribution to deploy, then print the live URL
  6. Update index.html and re-upload, then invalidate the CF cache
  7. List all objects in the bucket using a paginator

REQUIREMENTS:
  pip install boto3

SETUP:
  You need AWS credentials configured. Either:
    - Run `aws configure` (AWS CLI)
    - Or set environment variables:
        export AWS_ACCESS_KEY_ID=your_key
        export AWS_SECRET_ACCESS_KEY=your_secret
        export AWS_DEFAULT_REGION=eu-central-1   # or any region you prefer

  The IAM user/role needs these permissions:
    s3:CreateBucket, s3:PutObject, s3:PutBucketVersioning,
    s3:PutBucketPolicy, s3:ListBucket,
    cloudfront:CreateDistribution, cloudfront:CreateInvalidation,
    cloudfront:GetDistribution
"""

import boto3
import json
import time
import uuid

# ─── CONFIG ──────────────────────────────────────────────────────────────────
REGION      = "eu-central-1"          # Change to your preferred AWS region
BUCKET_NAME = f"demo-s3-cf-{uuid.uuid4().hex[:8]}"   # Unique bucket name
# ─────────────────────────────────────────────────────────────────────────────

s3 = boto3.client("s3", region_name=REGION)
cf = boto3.client("cloudfront", region_name="us-east-1")  # CF is always us-east-1


# ─── WEBSITE FILES ───────────────────────────────────────────────────────────
INDEX_HTML_V1 = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <title>AWS S3 + CloudFront Demo</title>
  <link rel="stylesheet" href="style.css" />
</head>
<body>
  <div class="card">
    <h1>🚀 Hello from S3 + CloudFront!</h1>
    <p>This page is hosted on <strong>Amazon S3</strong> and delivered via <strong>CloudFront</strong>.</p>
    <p class="version">Version 1 — original upload</p>
  </div>
</body>
</html>"""

INDEX_HTML_V2 = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <title>AWS S3 + CloudFront Demo</title>
  <link rel="stylesheet" href="style.css" />
</head>
<body>
  <div class="card">
    <h1>✅ Cache Invalidation Works!</h1>
    <p>This page was <strong>updated</strong> and the CloudFront cache was <strong>invalidated</strong>.</p>
    <p class="version">Version 2 — after invalidation</p>
  </div>
</body>
</html>"""

STYLE_CSS = """
body {
  font-family: 'Segoe UI', sans-serif;
  background: #0F2044;
  display: flex;
  justify-content: center;
  align-items: center;
  height: 100vh;
  margin: 0;
}
.card {
  background: white;
  border-radius: 12px;
  padding: 40px 60px;
  text-align: center;
  box-shadow: 0 8px 32px rgba(0,0,0,0.3);
  max-width: 500px;
}
h1 { color: #0F2044; margin-bottom: 16px; }
p  { color: #555; font-size: 1.05rem; line-height: 1.6; }
.version { margin-top: 24px; font-size: 0.85rem; color: #FF9900;
           font-weight: bold; letter-spacing: 1px; }
"""
# ─────────────────────────────────────────────────────────────────────────────


def step(n, title):
    print(f"\n{'─'*60}")
    print(f"  STEP {n}: {title}")
    print(f"{'─'*60}")


# ── STEP 1: Create S3 bucket with versioning ─────────────────────────────────
step(1, "Create S3 bucket with versioning")

bucket_config = {}
if REGION != "us-east-1":
    bucket_config = {"CreateBucketConfiguration": {"LocationConstraint": REGION}}

s3.create_bucket(Bucket=BUCKET_NAME, **bucket_config)
print(f"  ✓ Bucket created: {BUCKET_NAME}")

s3.put_bucket_versioning(
    Bucket=BUCKET_NAME,
    VersioningConfiguration={"Status": "Enabled"},
)
print("  ✓ Versioning enabled")

# Block all public access (OAC means CF handles access — not public URLs)
s3.put_public_access_block(
    Bucket=BUCKET_NAME,
    PublicAccessBlockConfiguration={
        "BlockPublicAcls": True,
        "IgnorePublicAcls": True,
        "BlockPublicPolicy": True,
        "RestrictPublicBuckets": True,
    },
)
print("  ✓ Public access blocked (OAC will be used instead)")


# ── STEP 2: Upload static website files ──────────────────────────────────────
step(2, "Upload static website files")

s3.put_object(
    Bucket=BUCKET_NAME,
    Key="index.html",
    Body=INDEX_HTML_V1.encode("utf-8"),
    ContentType="text/html",
)
print("  ✓ Uploaded index.html (v1)")

s3.put_object(
    Bucket=BUCKET_NAME,
    Key="style.css",
    Body=STYLE_CSS.encode("utf-8"),
    ContentType="text/css",
)
print("  ✓ Uploaded style.css")


# ── STEP 3: Create CloudFront distribution with OAC ──────────────────────────
step(3, "Create CloudFront distribution (OAC)")

# First, create an Origin Access Control
oac_response = cf.create_origin_access_control(
    OriginAccessControlConfig={
        "Name": f"OAC-{BUCKET_NAME}",
        "Description": "OAC for demo S3 bucket",
        "SigningProtocol": "sigv4",
        "SigningBehavior": "always",
        "OriginAccessControlOriginType": "s3",
    }
)
oac_id = oac_response["OriginAccessControl"]["Id"]
print(f"  ✓ Origin Access Control created: {oac_id}")

# Get account ID to build the S3 origin domain
s3_origin_domain = f"{BUCKET_NAME}.s3.{REGION}.amazonaws.com"

dist_response = cf.create_distribution(
    DistributionConfig={
        "CallerReference": str(uuid.uuid4()),
        "Comment": "Demo: S3 + CloudFront",
        "DefaultRootObject": "index.html",
        "Origins": {
            "Quantity": 1,
            "Items": [
                {
                    "Id": "s3-origin",
                    "DomainName": s3_origin_domain,
                    "S3OriginConfig": {"OriginAccessIdentity": ""},  # empty = use OAC
                    "OriginAccessControlId": oac_id,
                }
            ],
        },
        "DefaultCacheBehavior": {
            "TargetOriginId": "s3-origin",
            "ViewerProtocolPolicy": "redirect-to-https",
            "CachePolicyId": "658327ea-f89d-4fab-a63d-7e88639e58f6",  # CachingOptimized (managed)
            "AllowedMethods": {
                "Quantity": 2,
                "Items": ["GET", "HEAD"],
                "CachedMethods": {"Quantity": 2, "Items": ["GET", "HEAD"]},
            },
            "Compress": True,
        },
        "Enabled": True,
        "HttpVersion": "http2",
        "PriceClass": "PriceClass_100",  # US, Canada, Europe only (cheapest)
    }
)

dist_id     = dist_response["Distribution"]["Id"]
dist_domain = dist_response["Distribution"]["DomainName"]
dist_arn    = dist_response["Distribution"]["ARN"]
print(f"  ✓ Distribution created: {dist_id}")
print(f"  ✓ Domain: https://{dist_domain}")


# ── STEP 4: Attach OAC bucket policy so CF can read from S3 ──────────────────
step(4, "Attach OAC bucket policy")

# We need the AWS account ID to build the policy
sts = boto3.client("sts")
account_id = sts.get_caller_identity()["Account"]

bucket_policy = {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "AllowCloudFrontServicePrincipal",
            "Effect": "Allow",
            "Principal": {"Service": "cloudfront.amazonaws.com"},
            "Action": "s3:GetObject",
            "Resource": f"arn:aws:s3:::{BUCKET_NAME}/*",
            "Condition": {
                "StringEquals": {
                    "AWS:SourceArn": dist_arn
                }
            },
        }
    ],
}

s3.put_bucket_policy(
    Bucket=BUCKET_NAME,
    Policy=json.dumps(bucket_policy),
)
print("  ✓ Bucket policy applied — only CloudFront can read from S3")
print("  ✓ Direct S3 URL access will return 403 Forbidden")


# ── STEP 5: Wait for distribution to deploy ───────────────────────────────────
step(5, "Waiting for CloudFront distribution to deploy (~2-5 min)")
print("  (CloudFront propagates to 600+ edge locations globally)")

for i in range(60):          # wait up to 10 minutes
    status = cf.get_distribution(Id=dist_id)["Distribution"]["Status"]
    print(f"  ... Status: {status} ({i*10}s elapsed)", end="\r")
    if status == "Deployed":
        print(f"\n  ✓ Distribution deployed after ~{i*10}s")
        break
    time.sleep(10)
else:
    print("\n  ⚠  Timed out waiting — distribution may still be deploying.")
    print(f"     Check the AWS console: https://console.aws.amazon.com/cloudfront")

print(f"\n  🌍 Your live site: https://{dist_domain}")


# ── STEP 6: Update file and invalidate cache ──────────────────────────────────
step(6, "Update index.html and invalidate CloudFront cache")

s3.put_object(
    Bucket=BUCKET_NAME,
    Key="index.html",
    Body=INDEX_HTML_V2.encode("utf-8"),
    ContentType="text/html",
)
print("  ✓ index.html updated to v2")

inv_response = cf.create_invalidation(
    DistributionId=dist_id,
    InvalidationBatch={
        "Paths": {
            "Quantity": 1,
            "Items": ["/*"],       # invalidate everything
        },
        "CallerReference": f"invalidation-{uuid.uuid4().hex[:8]}",
    },
)
inv_id = inv_response["Invalidation"]["Id"]
print(f"  ✓ Cache invalidation created: {inv_id}")
print("  ✓ Edge caches will refresh within ~30 seconds")
print(f"  ✓ Reload https://{dist_domain} to see Version 2")


# ── STEP 7: List all objects in the bucket ────────────────────────────────────
step(7, "List all objects in the bucket (using paginator)")

paginator = s3.get_paginator("list_objects_v2")
pages     = paginator.paginate(Bucket=BUCKET_NAME)

print(f"  Objects in s3://{BUCKET_NAME}/")
print(f"  {'Key':<30} {'Size':>10}  {'Last Modified'}")
print(f"  {'─'*30} {'─'*10}  {'─'*20}")

total_objects = 0
for page in pages:
    for obj in page.get("Contents", []):
        print(f"  {obj['Key']:<30} {obj['Size']:>8} B  {obj['LastModified'].strftime('%Y-%m-%d %H:%M:%S')}")
        total_objects += 1

print(f"\n  Total: {total_objects} object(s)")


# ── SUMMARY ───────────────────────────────────────────────────────────────────
print(f"""
{'='*60}
  DEMO COMPLETE
{'='*60}
  Bucket:        s3://{BUCKET_NAME}
  Region:        {REGION}
  CloudFront ID: {dist_id}
  Live URL:      https://{dist_domain}

  CLEANUP (to avoid AWS charges):
    Run cleanup.py  — or manually:
      1. Delete CloudFront distribution (must disable first)
      2. Empty and delete the S3 bucket
{'='*60}
""")
