# AWS S3 + CloudFront Demo

A complete, runnable Python demo for the SE4458 assignment.

## What it demonstrates

| Step | What happens |
|------|-------------|
| 1 | Creates an S3 bucket with versioning + blocks public access |
| 2 | Uploads `index.html` and `style.css` (a real webpage) |
| 3 | Creates a CloudFront distribution with **Origin Access Control (OAC)** |
| 4 | Attaches a bucket policy so only CloudFront can read from S3 |
| 5 | Waits for the distribution to deploy, then prints the live URL |
| 6 | Updates `index.html` to v2 and runs a cache invalidation (`/*`) |
| 7 | Lists all bucket objects using a boto3 paginator |

## Setup

### 1. Install dependencies
```bash
pip install boto3
```

### 2. Configure AWS credentials
```bash
aws configure
# Enter your Access Key ID, Secret Access Key, and region (e.g. eu-central-1)
```

Or set environment variables:
```bash
export AWS_ACCESS_KEY_ID=your_key
export AWS_SECRET_ACCESS_KEY=your_secret
export AWS_DEFAULT_REGION=eu-central-1
```

### 3. Required IAM permissions
Your AWS user needs:
- `s3:CreateBucket`, `s3:PutObject`, `s3:PutBucketVersioning`, `s3:PutBucketPolicy`, `s3:PutPublicAccessBlock`, `s3:ListBucket`, `s3:DeleteObject`, `s3:DeleteBucket`
- `cloudfront:CreateOriginAccessControl`, `cloudfront:CreateDistribution`, `cloudfront:CreateInvalidation`, `cloudfront:GetDistribution`, `cloudfront:UpdateDistribution`, `cloudfront:DeleteDistribution`
- `sts:GetCallerIdentity`

## Run the demo

```bash
python demo.py
```

Expected output:
```
────────────────────────────────────────────────────────────
  STEP 1: Create S3 bucket with versioning
────────────────────────────────────────────────────────────
  ✓ Bucket created: demo-s3-cf-a1b2c3d4
  ✓ Versioning enabled
  ✓ Public access blocked
...
  🌍 Your live site: https://d1234abcd.cloudfront.net
...
============================================================
  DEMO COMPLETE
============================================================
```

## Cleanup (important!)

After the demo, run cleanup to avoid AWS charges:

```bash
python cleanup.py <BUCKET_NAME> <DISTRIBUTION_ID>
# Example:
python cleanup.py demo-s3-cf-a1b2c3d4 E1A2B3C4D5EXMP
```

The bucket name and distribution ID are printed at the end of `demo.py`.

## Notes

- CloudFront distribution deployment takes **2–5 minutes** (step 5 polls automatically)
- The demo uses `PriceClass_100` (US + Europe edge locations only) to minimize cost
- Cache invalidation (`/*`) takes ~30 seconds to propagate
- Direct S3 URLs return **403 Forbidden** — only the CloudFront URL works (OAC)
