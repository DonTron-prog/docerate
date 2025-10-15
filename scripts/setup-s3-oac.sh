#!/bin/bash
set -e

# Script to secure S3 bucket with Origin Access Control (OAC)
# This replaces public S3 access with CloudFront-only access using OAC

echo "========================================"
echo "Setting up S3 Origin Access Control"
echo "========================================"
echo ""
echo "This script will:"
echo "1. Create Origin Access Control (OAC)"
echo "2. Update CloudFront S3 origin (website → REST API endpoint)"
echo "3. Update S3 bucket policy (public → CloudFront-only)"
echo "4. Enable S3 Block Public Access"
echo "5. Disable S3 static website hosting"
echo "6. Configure CloudFront custom error pages for SPA"
echo ""

# Configuration
FRONTEND_BUCKET=${FRONTEND_BUCKET:-"docerate-frontend"}
CLOUDFRONT_DIST_ID=${CLOUDFRONT_DIST_ID:-"E3FV2HGEXHUM2J"}
OAC_NAME=${OAC_NAME:-"docerate-frontend-oac"}
AWS_REGION=${AWS_REGION:-"us-east-1"}
AWS_PROFILE=${AWS_PROFILE:-"default"}

echo "Configuration:"
echo "  S3 Bucket: $FRONTEND_BUCKET"
echo "  CloudFront Distribution: $CLOUDFRONT_DIST_ID"
echo "  OAC Name: $OAC_NAME"
echo "  AWS Region: $AWS_REGION"
echo "  AWS Profile: $AWS_PROFILE"
echo ""

# Confirm before proceeding
read -p "This will modify CloudFront and S3 settings. Continue? (y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Operation cancelled."
    exit 0
fi
echo ""

# ============================================
# Step 1: Create Origin Access Control (OAC)
# ============================================
echo "Step 1: Creating Origin Access Control..."

# Check if OAC already exists
EXISTING_OAC_ID=$(aws cloudfront list-origin-access-controls \
    --profile $AWS_PROFILE \
    --output json | jq -r ".OriginAccessControlList.Items[] | select(.Name == \"$OAC_NAME\") | .Id" || echo "")

if [ -n "$EXISTING_OAC_ID" ]; then
    echo "  ✓ OAC already exists: $EXISTING_OAC_ID"
    OAC_ID="$EXISTING_OAC_ID"
else
    echo "  Creating new OAC: $OAC_NAME"

    # Create OAC configuration
    cat > /tmp/oac-config.json << EOF
{
    "Name": "$OAC_NAME",
    "Description": "Origin Access Control for $FRONTEND_BUCKET S3 bucket",
    "SigningProtocol": "sigv4",
    "SigningBehavior": "always",
    "OriginAccessControlOriginType": "s3"
}
EOF

    # Create OAC
    OAC_RESULT=$(aws cloudfront create-origin-access-control \
        --origin-access-control-config file:///tmp/oac-config.json \
        --profile $AWS_PROFILE \
        --output json)

    OAC_ID=$(echo "$OAC_RESULT" | jq -r '.OriginAccessControl.Id')
    echo "  ✓ Created OAC: $OAC_ID"
    rm /tmp/oac-config.json
fi

echo ""

# ============================================
# Step 2: Update CloudFront Distribution
# ============================================
echo "Step 2: Updating CloudFront distribution..."

# Get current distribution configuration
aws cloudfront get-distribution-config \
    --id $CLOUDFRONT_DIST_ID \
    --profile $AWS_PROFILE \
    --output json > /tmp/cloudfront-config.json

# Extract ETag and config
ETAG=$(cat /tmp/cloudfront-config.json | jq -r '.ETag')
cat /tmp/cloudfront-config.json | jq '.DistributionConfig' > /tmp/cloudfront-dist-config.json

echo "  Current ETag: $ETAG"

# Update S3 origin to use REST API endpoint and OAC
echo "  Updating S3 origin configuration..."
cat /tmp/cloudfront-dist-config.json | jq \
    --arg bucket "$FRONTEND_BUCKET" \
    --arg domain "$FRONTEND_BUCKET.s3.$AWS_REGION.amazonaws.com" \
    --arg oac_id "$OAC_ID" \
    '
    .Origins.Items |= map(
        if .Id == "S3-\($bucket)" then
            {
                "Id": .Id,
                "DomainName": $domain,
                "OriginPath": "",
                "CustomHeaders": {
                    "Quantity": 0
                },
                "S3OriginConfig": {
                    "OriginAccessIdentity": ""
                },
                "ConnectionAttempts": 3,
                "ConnectionTimeout": 10,
                "OriginShield": {
                    "Enabled": false
                },
                "OriginAccessControlId": $oac_id
            }
        else
            .
        end
    )
    ' > /tmp/cloudfront-dist-config-updated.json

mv /tmp/cloudfront-dist-config-updated.json /tmp/cloudfront-dist-config.json

# Configure custom error pages for SPA routing
echo "  Configuring custom error pages for React SPA..."
cat /tmp/cloudfront-dist-config.json | jq '
    .CustomErrorResponses = {
        "Quantity": 2,
        "Items": [
            {
                "ErrorCode": 403,
                "ResponsePagePath": "/index.html",
                "ResponseCode": "200",
                "ErrorCachingMinTTL": 300
            },
            {
                "ErrorCode": 404,
                "ResponsePagePath": "/index.html",
                "ResponseCode": "200",
                "ErrorCachingMinTTL": 300
            }
        ]
    }
    ' > /tmp/cloudfront-dist-config-updated.json

mv /tmp/cloudfront-dist-config-updated.json /tmp/cloudfront-dist-config.json

# Update the distribution
echo "  Applying changes to CloudFront..."
aws cloudfront update-distribution \
    --id $CLOUDFRONT_DIST_ID \
    --distribution-config file:///tmp/cloudfront-dist-config.json \
    --if-match "$ETAG" \
    --profile $AWS_PROFILE \
    --output json > /tmp/cloudfront-update-result.json

echo "  ✓ CloudFront update initiated"
echo ""

# ============================================
# Step 3: Wait for CloudFront to Deploy
# ============================================
echo "Step 3: Waiting for CloudFront to deploy..."
echo "  This typically takes 5-15 minutes."
echo "  You must wait for this to complete before updating S3 policy."
echo ""

aws cloudfront wait distribution-deployed \
    --id $CLOUDFRONT_DIST_ID \
    --profile $AWS_PROFILE

echo "  ✓ CloudFront deployment complete!"
echo ""

# ============================================
# Step 4: Update S3 Bucket Policy
# ============================================
echo "Step 4: Updating S3 bucket policy..."

# Get CloudFront distribution ARN
DISTRIBUTION_ARN="arn:aws:cloudfront::$(aws sts get-caller-identity --profile $AWS_PROFILE --query Account --output text):distribution/$CLOUDFRONT_DIST_ID"

# Create OAC-based bucket policy
cat > /tmp/bucket-policy.json << EOF
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
            "Resource": "arn:aws:s3:::$FRONTEND_BUCKET/*",
            "Condition": {
                "StringEquals": {
                    "AWS:SourceArn": "$DISTRIBUTION_ARN"
                }
            }
        }
    ]
}
EOF

# Apply bucket policy
aws s3api put-bucket-policy \
    --bucket $FRONTEND_BUCKET \
    --policy file:///tmp/bucket-policy.json \
    --profile $AWS_PROFILE

echo "  ✓ S3 bucket policy updated (CloudFront-only access)"
rm /tmp/bucket-policy.json
echo ""

# ============================================
# Step 5: Enable Block Public Access
# ============================================
echo "Step 5: Enabling S3 Block Public Access..."

aws s3api put-public-access-block \
    --bucket $FRONTEND_BUCKET \
    --public-access-block-configuration \
        "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true" \
    --profile $AWS_PROFILE

echo "  ✓ Block Public Access enabled (all settings)"
echo ""

# ============================================
# Step 6: Disable Static Website Hosting
# ============================================
echo "Step 6: Disabling S3 static website hosting..."

aws s3api delete-bucket-website \
    --bucket $FRONTEND_BUCKET \
    --profile $AWS_PROFILE

echo "  ✓ Static website hosting disabled"
echo ""

# ============================================
# Step 7: Verify Configuration
# ============================================
echo "Step 7: Verifying configuration..."

# Get CloudFront domain
CLOUDFRONT_DOMAIN=$(aws cloudfront get-distribution \
    --id $CLOUDFRONT_DIST_ID \
    --profile $AWS_PROFILE \
    --query 'Distribution.DomainName' \
    --output text)

echo ""
echo "========================================"
echo "S3 Security Setup Complete!"
echo "========================================"
echo ""
echo "Configuration Summary:"
echo "  ✓ Origin Access Control: $OAC_ID"
echo "  ✓ CloudFront Distribution: $CLOUDFRONT_DIST_ID"
echo "  ✓ S3 Bucket: $FRONTEND_BUCKET"
echo "  ✓ Block Public Access: Enabled"
echo "  ✓ Website Hosting: Disabled"
echo "  ✓ Custom Error Pages: Configured (403/404 → /index.html)"
echo ""
echo "Security Status:"
echo "  ✅ S3 bucket is now PRIVATE (CloudFront-only access)"
echo "  ✅ Direct S3 URLs will return 403 Forbidden"
echo "  ✅ Content served only through CloudFront"
echo ""
echo "Testing:"
echo "  CloudFront URL: https://$CLOUDFRONT_DOMAIN"
echo ""
echo "Verification Commands:"
echo "  # Should work (200 OK):"
echo "  curl -I https://$CLOUDFRONT_DOMAIN"
echo ""
echo "  # Should fail (403 Forbidden):"
echo "  curl -I https://$FRONTEND_BUCKET.s3.amazonaws.com/index.html"
echo ""
echo "Next Steps:"
echo "  1. Test your site: https://$CLOUDFRONT_DOMAIN"
echo "  2. Verify direct S3 access is blocked"
echo "  3. Test React SPA routing (should work via error pages)"
echo "  4. Deploy updates normally - your scripts will continue to work"
echo ""

# Clean up temp files
rm -f /tmp/cloudfront-*.json

echo "Done!"
