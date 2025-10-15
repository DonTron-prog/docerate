# S3 Security with Origin Access Control (OAC)

This document explains how the `docerate-frontend` S3 bucket is secured using AWS Origin Access Control (OAC) to ensure content is only accessible through CloudFront.

## Table of Contents
- [Security Architecture](#security-architecture)
- [What is Origin Access Control (OAC)?](#what-is-origin-access-control-oac)
- [Why This Matters](#why-this-matters)
- [Implementation Details](#implementation-details)
- [Verification](#verification)
- [Impact on Deployment](#impact-on-deployment)
- [Troubleshooting](#troubleshooting)
- [Rollback Procedure](#rollback-procedure)

## Security Architecture

### Before OAC (Insecure)
```
User → CloudFront (d2w8hymo03zbys.cloudfront.net) → S3 (WORKS)
User → S3 Direct (docerate-frontend.s3.amazonaws.com) → S3 (WORKS) ❌ Security Gap!
```

Anyone could bypass CloudFront and access S3 directly, bypassing:
- CloudFront caching and performance
- CloudFront access logging
- Future WAF rules or security controls
- Your monitoring and analytics

### After OAC (Secure)
```
User → CloudFront (d2w8hymo03zbys.cloudfront.net) → S3 (WORKS) ✅
User → S3 Direct (docerate-frontend.s3.amazonaws.com) → 403 Forbidden ✅
```

S3 bucket is completely private and only accepts requests from your specific CloudFront distribution using cryptographic signatures.

## What is Origin Access Control (OAC)?

Origin Access Control (OAC) is AWS's modern authentication mechanism for CloudFront to access private S3 buckets.

### How It Works

1. **OAC Identity Created**: A special identity (`E1FNALM72KAMN1`) is created in CloudFront
2. **CloudFront Signs Requests**: CloudFront uses AWS Signature Version 4 (sigv4) to cryptographically sign every request to S3
3. **S3 Verifies Signatures**: S3 bucket policy only allows requests from CloudFront distribution `E3FV2HGEXHUM2J` with valid OAC signatures
4. **Public Access Blocked**: S3 Block Public Access ensures no anonymous requests succeed

### OAC vs OAI (Legacy)

| Feature | OAC (Current) | OAI (Deprecated) |
|---------|---------------|------------------|
| Signing Protocol | AWS Signature v4 | Legacy signing |
| SSE-KMS Support | ✅ Yes | ❌ No |
| All S3 Regions | ✅ Yes | ⚠️ Limited |
| AWS Recommendation | ✅ Recommended | ⚠️ Deprecated |
| Future Support | ✅ Active | ⚠️ End of life |

**OAC is the modern, AWS-recommended approach and replaces the deprecated Origin Access Identity (OAI).**

## Why This Matters

### Security Benefits

1. **Zero-Trust Architecture**: S3 bucket is completely private by default
2. **Defense in Depth**: Even if CloudFront is misconfigured, S3 blocks public access
3. **Prevent Bandwidth Theft**: Users can't bypass CloudFront to consume S3 bandwidth directly
4. **Audit Trail**: All access goes through CloudFront where it can be logged and monitored
5. **Foundation for Advanced Security**: Required before adding WAF rules, rate limiting, geo-blocking

### Cost Benefits

- Prevents unauthorized direct S3 access that could incur unexpected charges
- Ensures all traffic goes through CloudFront caching, reducing S3 requests

### Compliance Benefits

- Follows AWS Well-Architected Framework security best practices
- Enables centralized access logging at CloudFront level
- Supports future compliance requirements (PCI-DSS, SOC 2, etc.)

## Implementation Details

### Configuration Applied

The setup script (`scripts/setup-s3-oac.sh`) configured the following:

#### 1. Origin Access Control
```
OAC ID: E1FNALM72KAMN1
Name: docerate-frontend-oac
Signing Protocol: sigv4
Signing Behavior: always
Origin Type: s3
```

#### 2. CloudFront Origin Configuration
```
Origin Domain: docerate-frontend.s3.us-east-1.amazonaws.com
Origin Type: S3OriginConfig (REST API endpoint)
OAC ID: E1FNALM72KAMN1
Protocol: HTTPS only
```

**Changed from:**
- Website endpoint: `docerate-frontend.s3-website-us-east-1.amazonaws.com`
- Origin type: `CustomOriginConfig` (HTTP)

**Changed to:**
- REST API endpoint: `docerate-frontend.s3.us-east-1.amazonaws.com`
- Origin type: `S3OriginConfig` (native S3 integration with OAC)

#### 3. S3 Bucket Policy
```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "AllowCloudFrontServicePrincipalReadOnly",
            "Effect": "Allow",
            "Principal": {
                "Service": "cloudfront.amazonaws.com"
            },
            "Action": "s3:GetObject",
            "Resource": "arn:aws:s3:::docerate-frontend/*",
            "Condition": {
                "StringEquals": {
                    "AWS:SourceArn": "arn:aws:cloudfront::083994718303:distribution/E3FV2HGEXHUM2J"
                }
            }
        }
    ]
}
```

**Key Points:**
- Principal is CloudFront service (not `"*"` for public)
- Condition restricts access to specific CloudFront distribution
- Only `s3:GetObject` permission (read-only)

#### 4. S3 Block Public Access
All four settings enabled:
```
BlockPublicAcls: true
IgnorePublicAcls: true
BlockPublicPolicy: true
RestrictPublicBuckets: true
```

This ensures no accidental public access through ACLs or future policy changes.

#### 5. S3 Static Website Hosting
**Disabled** - No longer needed because:
- CloudFront handles all routing via custom error pages
- S3 REST API endpoint is more secure than website endpoint
- React SPA routing handled by CloudFront error pages (403/404 → /index.html)

#### 6. CloudFront Custom Error Pages
Configured for React SPA routing:
```
403 Forbidden → /index.html (HTTP 200)
404 Not Found → /index.html (HTTP 200)
Error Caching: 300 seconds (5 minutes)
```

This ensures React Router works correctly when users directly access deep links like `/posts/my-article`.

## Verification

### Automated Tests

The setup script provides verification commands:

```bash
# Test CloudFront access (should return 200 OK)
curl -I https://d2w8hymo03zbys.cloudfront.net

# Test direct S3 access (should return 403 Forbidden)
curl -I https://docerate-frontend.s3.amazonaws.com/index.html
```

### Manual Testing Checklist

- [ ] CloudFront URL loads: https://d2w8hymo03zbys.cloudfront.net
- [ ] React SPA routing works (test deep links)
- [ ] Direct S3 URL returns 403: https://docerate-frontend.s3.amazonaws.com/index.html
- [ ] S3 website endpoint returns 404: http://docerate-frontend.s3-website-us-east-1.amazonaws.com
- [ ] Deployment scripts still work: `./scripts/deploy-frontend.sh`
- [ ] API calls through CloudFront work: https://d2w8hymo03zbys.cloudfront.net/api/tags

### AWS Console Verification

**CloudFront Distribution (E3FV2HGEXHUM2J):**
1. Go to CloudFront → Distributions → E3FV2HGEXHUM2J
2. Origins tab → S3 origin should show:
   - Domain: `docerate-frontend.s3.us-east-1.amazonaws.com`
   - Origin access: Origin access control
   - OAC: `docerate-frontend-oac`
3. Error pages tab should show:
   - 403 → /index.html (200)
   - 404 → /index.html (200)

**S3 Bucket (docerate-frontend):**
1. Go to S3 → docerate-frontend
2. Permissions tab → Bucket policy should reference CloudFront service principal
3. Permissions tab → Block public access should show "On" for all 4 settings
4. Properties tab → Static website hosting should show "Disabled"

**Origin Access Control:**
1. Go to CloudFront → Origin access → Origin access controls
2. Should see: `docerate-frontend-oac` (E1FNALM72KAMN1)
3. Used by distribution: E3FV2HGEXHUM2J

## Impact on Deployment

### ✅ No Changes Required to Deployment Workflows

Your existing deployment scripts continue to work without modification:

```bash
# Frontend deployment (still works)
FRONTEND_BUCKET=docerate-frontend \
CLOUDFRONT_DIST_ID=E3FV2HGEXHUM2J \
./scripts/deploy-frontend.sh

# RAG data deployment (still works)
S3_BUCKET=docerate-rag-data \
./scripts/deploy-data.sh
```

### Why Deployment Still Works

**What got blocked:**
- Anonymous HTTP requests to S3 URLs
- Public internet access to bucket

**What still works:**
- Authenticated AWS CLI commands (`aws s3 sync`, `aws s3 cp`)
- IAM user/role credentials for S3 API access
- CloudFront accessing S3 via OAC signatures

Your deployment scripts use AWS CLI with IAM credentials, which are completely separate from anonymous public access. The S3 bucket policy and Block Public Access only affect anonymous HTTP requests, not authenticated API calls.

### IAM Permissions Required

Your IAM user/role needs these permissions for deployment (unchanged):

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "s3:PutObject",
                "s3:GetObject",
                "s3:DeleteObject",
                "s3:ListBucket"
            ],
            "Resource": [
                "arn:aws:s3:::docerate-frontend",
                "arn:aws:s3:::docerate-frontend/*"
            ]
        },
        {
            "Effect": "Allow",
            "Action": [
                "cloudfront:CreateInvalidation"
            ],
            "Resource": "arn:aws:cloudfront::083994718303:distribution/E3FV2HGEXHUM2J"
        }
    ]
}
```

## Troubleshooting

### Site Not Loading Through CloudFront

**Symptoms:**
- CloudFront URL returns errors
- Console shows network errors

**Diagnosis:**
```bash
# Check CloudFront distribution status
aws cloudfront get-distribution --id E3FV2HGEXHUM2J --query 'Distribution.Status'

# Should return: "Deployed"
# If "InProgress", wait for deployment to complete
```

**Solution:**
- Wait for CloudFront deployment to finish (5-15 minutes)
- Check CloudFront error pages are configured correctly
- Verify OAC is attached to S3 origin

### Direct S3 Access Still Works

**Symptoms:**
- Direct S3 URLs return 200 instead of 403
- Security not properly configured

**Diagnosis:**
```bash
# Check Block Public Access settings
aws s3api get-public-access-block --bucket docerate-frontend

# Should show all "true":
# BlockPublicAcls: true
# IgnorePublicAcls: true
# BlockPublicPolicy: true
# RestrictPublicBuckets: true

# Check bucket policy
aws s3api get-bucket-policy --bucket docerate-frontend
# Should show CloudFront service principal, not "*"
```

**Solution:**
Run the setup script again to ensure all settings are applied:
```bash
./scripts/setup-s3-oac.sh
```

### React SPA Routes Return 404

**Symptoms:**
- Direct access to `/posts/my-article` returns 404
- Only homepage works

**Diagnosis:**
```bash
# Check CloudFront custom error pages
aws cloudfront get-distribution-config --id E3FV2HGEXHUM2J \
  --query 'DistributionConfig.CustomErrorResponses'

# Should show 403 and 404 configured to return /index.html
```

**Solution:**
Custom error pages may not be configured. Update CloudFront:
```bash
# Re-run setup script to configure error pages
./scripts/setup-s3-oac.sh
```

### Deployment Scripts Failing

**Symptoms:**
- `deploy-frontend.sh` returns permission errors
- Cannot upload to S3

**Diagnosis:**
```bash
# Test IAM credentials
aws sts get-caller-identity

# Test S3 write access
aws s3 cp /tmp/test.txt s3://docerate-frontend/test.txt
aws s3 rm s3://docerate-frontend/test.txt
```

**Solution:**
OAC only blocks anonymous public access, not IAM-authenticated API calls. If deployment fails:
1. Verify AWS credentials are configured: `aws configure list`
2. Verify IAM user/role has S3 write permissions
3. Check for typos in bucket name or region

### CloudFront Returns 502/503 Errors

**Symptoms:**
- CloudFront URL returns server errors
- Site was working before OAC setup

**Diagnosis:**
```bash
# Check S3 bucket policy allows CloudFront
aws s3api get-bucket-policy --bucket docerate-frontend

# Verify OAC ID matches
aws cloudfront get-distribution-config --id E3FV2HGEXHUM2J \
  --query 'DistributionConfig.Origins.Items[?Id==`S3-docerate-frontend`].OriginAccessControlId'
```

**Solution:**
S3 bucket policy may not allow the OAC. Update policy:
```bash
# Get CloudFront distribution ARN
DISTRIBUTION_ARN="arn:aws:cloudfront::083994718303:distribution/E3FV2HGEXHUM2J"

# Update S3 bucket policy (see Implementation Details section for full policy)
aws s3api put-bucket-policy --bucket docerate-frontend --policy file://bucket-policy.json
```

## Rollback Procedure

If you need to revert to public S3 access (not recommended):

### 1. Remove OAC from CloudFront

```bash
# Get current distribution config
aws cloudfront get-distribution-config --id E3FV2HGEXHUM2J --output json > /tmp/cf-config.json

# Extract ETag and config
ETAG=$(cat /tmp/cf-config.json | jq -r '.ETag')
cat /tmp/cf-config.json | jq '.DistributionConfig' > /tmp/cf-dist-config.json

# Remove OAC from S3 origin
cat /tmp/cf-dist-config.json | jq '
  .Origins.Items |= map(
    if .Id == "S3-docerate-frontend" then
      .OriginAccessControlId = ""
    else
      .
    end
  )
' > /tmp/cf-dist-config-updated.json

# Update distribution
aws cloudfront update-distribution \
  --id E3FV2HGEXHUM2J \
  --distribution-config file:///tmp/cf-dist-config-updated.json \
  --if-match "$ETAG"

# Wait for deployment
aws cloudfront wait distribution-deployed --id E3FV2HGEXHUM2J
```

### 2. Re-enable S3 Public Access

```bash
# Disable Block Public Access
aws s3api put-public-access-block \
  --bucket docerate-frontend \
  --public-access-block-configuration \
    "BlockPublicAcls=false,IgnorePublicAcls=false,BlockPublicPolicy=false,RestrictPublicBuckets=false"

# Apply public bucket policy
cat > /tmp/public-policy.json << 'EOF'
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "PublicReadGetObject",
            "Effect": "Allow",
            "Principal": "*",
            "Action": "s3:GetObject",
            "Resource": "arn:aws:s3:::docerate-frontend/*"
        }
    ]
}
EOF

aws s3api put-bucket-policy \
  --bucket docerate-frontend \
  --policy file:///tmp/public-policy.json

# Re-enable static website hosting
aws s3api put-bucket-website \
  --bucket docerate-frontend \
  --website-configuration '{
    "IndexDocument": {"Suffix": "index.html"},
    "ErrorDocument": {"Key": "index.html"}
  }'
```

### 3. Update CloudFront Origin to Website Endpoint

```bash
# Update origin to use website endpoint instead of REST API
# (Follow similar process as step 1, changing DomainName to s3-website endpoint)
```

**⚠️ Warning:** Reverting to public S3 access removes important security protections. Only do this for testing or troubleshooting.

## Best Practices

### Ongoing Security

1. **Monitor CloudFront Access Logs**: Enable CloudFront access logging to track all requests
2. **Set Up CloudWatch Alarms**: Alert on unexpected 403 errors or traffic patterns
3. **Regular Security Audits**: Review S3 bucket policies and CloudFront configurations quarterly
4. **Principle of Least Privilege**: Ensure IAM roles only have required S3 permissions

### Future Enhancements

With OAC in place, you can now add:

1. **AWS WAF**: Add web application firewall rules to CloudFront
2. **Rate Limiting**: Implement request throttling at CloudFront edge
3. **Geo-Blocking**: Restrict access by geographic region
4. **Signed URLs**: Implement time-limited access to specific content
5. **Enhanced Logging**: Capture detailed access logs for security analysis

### Cost Optimization

- CloudFront caching reduces S3 GET requests
- OAC prevents unauthorized bandwidth consumption
- Consider CloudFront edge caching policies for further optimization

## Additional Resources

- [AWS Documentation: Origin Access Control](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/private-content-restricting-access-to-s3.html)
- [AWS Security Best Practices for S3](https://docs.aws.amazon.com/AmazonS3/latest/userguide/security-best-practices.html)
- [CloudFront Custom Error Pages](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/GeneratingCustomErrorResponses.html)

## Summary

Origin Access Control (OAC) provides modern, secure, and AWS-recommended authentication between CloudFront and S3. The implementation:

✅ Blocks all direct S3 access (403 Forbidden)
✅ Allows CloudFront access via cryptographic signatures
✅ Maintains all deployment workflows unchanged
✅ Enables advanced security features like WAF
✅ Follows AWS Well-Architected Framework
✅ Supports React SPA routing via custom error pages

Your S3 bucket is now secured with zero-trust architecture while maintaining the same developer experience for deployments.
