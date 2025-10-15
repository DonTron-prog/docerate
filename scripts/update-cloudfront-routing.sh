#!/bin/bash
set -e

# Script to update CloudFront distribution with API Gateway routing
# This eliminates CORS by routing /api/* through CloudFront to API Gateway

echo "========================================"
echo "Updating CloudFront API Routing"
echo "========================================"

# Configuration
CLOUDFRONT_DIST_ID=${CLOUDFRONT_DIST_ID:-"E3FV2HGEXHUM2J"}
API_GATEWAY_ID=${API_GATEWAY_ID:-"9o9ra1wg7f"}
API_STAGE=${API_STAGE:-"prod"}
AWS_REGION=${AWS_REGION:-"us-east-1"}
AWS_PROFILE=${AWS_PROFILE:-"default"}

echo "CloudFront Distribution: $CLOUDFRONT_DIST_ID"
echo "API Gateway: $API_GATEWAY_ID"
echo "API Stage: $API_STAGE"
echo ""

# Get current distribution configuration
echo "Fetching current CloudFront configuration..."
aws cloudfront get-distribution-config \
    --id $CLOUDFRONT_DIST_ID \
    --profile $AWS_PROFILE \
    --output json > /tmp/cloudfront-config.json

# Extract ETag and config
ETAG=$(cat /tmp/cloudfront-config.json | jq -r '.ETag')
cat /tmp/cloudfront-config.json | jq '.DistributionConfig' > /tmp/cloudfront-dist-config.json

echo "Current ETag: $ETAG"

# Check if API Gateway origin already exists
EXISTING_API_ORIGIN=$(cat /tmp/cloudfront-dist-config.json | jq -r '.Origins.Items[] | select(.Id == "api-gateway-origin") | .Id' || echo "")

if [ -n "$EXISTING_API_ORIGIN" ]; then
    echo "API Gateway origin already exists. Updating configuration..."
else
    echo "Adding API Gateway as new origin..."

    # Add API Gateway origin
    cat /tmp/cloudfront-dist-config.json | jq \
        --arg api_domain "$API_GATEWAY_ID.execute-api.$AWS_REGION.amazonaws.com" \
        --arg origin_path "/$API_STAGE" \
        '.Origins.Quantity += 1 |
         .Origins.Items += [{
            "Id": "api-gateway-origin",
            "DomainName": $api_domain,
            "OriginPath": $origin_path,
            "CustomHeaders": {
                "Quantity": 0
            },
            "CustomOriginConfig": {
                "HTTPPort": 80,
                "HTTPSPort": 443,
                "OriginProtocolPolicy": "https-only",
                "OriginSslProtocols": {
                    "Quantity": 3,
                    "Items": ["TLSv1", "TLSv1.1", "TLSv1.2"]
                },
                "OriginReadTimeout": 60,
                "OriginKeepaliveTimeout": 5
            },
            "ConnectionAttempts": 3,
            "ConnectionTimeout": 10,
            "OriginShield": {
                "Enabled": false
            },
            "OriginAccessControlId": ""
        }]' > /tmp/cloudfront-dist-config-updated.json

    mv /tmp/cloudfront-dist-config-updated.json /tmp/cloudfront-dist-config.json
fi

# Check if /api/* cache behavior already exists
EXISTING_API_BEHAVIOR=$(cat /tmp/cloudfront-dist-config.json | jq -r '.CacheBehaviors.Items[]? | select(.PathPattern == "/api/*") | .PathPattern' || echo "")

if [ -n "$EXISTING_API_BEHAVIOR" ]; then
    echo "API cache behavior already exists. Configuration up to date."
else
    echo "Adding cache behavior for /api/* paths..."

    # Add cache behavior for /api/* paths
    cat /tmp/cloudfront-dist-config.json | jq \
        '.CacheBehaviors.Quantity += 1 |
         .CacheBehaviors.Items += [{
            "PathPattern": "/api/*",
            "TargetOriginId": "api-gateway-origin",
            "TrustedSigners": {
                "Enabled": false,
                "Quantity": 0
            },
            "TrustedKeyGroups": {
                "Enabled": false,
                "Quantity": 0
            },
            "ViewerProtocolPolicy": "https-only",
            "AllowedMethods": {
                "Quantity": 7,
                "Items": ["HEAD", "DELETE", "POST", "GET", "OPTIONS", "PUT", "PATCH"],
                "CachedMethods": {
                    "Quantity": 2,
                    "Items": ["HEAD", "GET"]
                }
            },
            "SmoothStreaming": false,
            "Compress": true,
            "LambdaFunctionAssociations": {
                "Quantity": 0
            },
            "FunctionAssociations": {
                "Quantity": 0
            },
            "FieldLevelEncryptionId": "",
            "GrpcConfig": {
                "Enabled": false
            },
            "ForwardedValues": {
                "QueryString": true,
                "Cookies": {
                    "Forward": "all"
                },
                "Headers": {
                    "Quantity": 10,
                    "Items": [
                        "Accept",
                        "Accept-Charset",
                        "Accept-Language",
                        "Authorization",
                        "Content-Type",
                        "Origin",
                        "Referer",
                        "User-Agent",
                        "X-Forwarded-For",
                        "X-Request-Id"
                    ]
                },
                "QueryStringCacheKeys": {
                    "Quantity": 0
                }
            },
            "MinTTL": 0,
            "DefaultTTL": 0,
            "MaxTTL": 0
        }]' > /tmp/cloudfront-dist-config-updated.json

    mv /tmp/cloudfront-dist-config-updated.json /tmp/cloudfront-dist-config.json
fi

# Update the distribution
echo ""
echo "Updating CloudFront distribution..."
aws cloudfront update-distribution \
    --id $CLOUDFRONT_DIST_ID \
    --distribution-config file:///tmp/cloudfront-dist-config.json \
    --if-match "$ETAG" \
    --profile $AWS_PROFILE \
    --output json > /tmp/cloudfront-update-result.json

echo "Update initiated successfully!"
echo ""
echo "Waiting for distribution to deploy (this may take 5-15 minutes)..."
echo "You can check status with: aws cloudfront get-distribution --id $CLOUDFRONT_DIST_ID --profile $AWS_PROFILE"
echo ""

# Optional: Wait for deployment to complete (can take a while)
read -p "Wait for deployment to complete? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Waiting for deployment..."
    aws cloudfront wait distribution-deployed \
        --id $CLOUDFRONT_DIST_ID \
        --profile $AWS_PROFILE
    echo "Deployment complete!"
fi

# Clean up
rm -f /tmp/cloudfront-*.json

echo ""
echo "========================================"
echo "CloudFront Update Complete!"
echo "========================================"
echo ""
echo "Your CloudFront distribution now routes:"
echo "  /* → S3 (frontend static files)"
echo "  /api/* → API Gateway → Lambda"
echo ""
echo "Next steps:"
echo "1. Deploy updated frontend: FRONTEND_BUCKET=docerate-frontend CLOUDFRONT_DIST_ID=$CLOUDFRONT_DIST_ID ./scripts/deploy-frontend.sh"
echo "2. Test API calls (should be same-origin, no CORS)"
echo "3. Verify no CORS errors in browser console"
echo ""
echo "CloudFront URL: https://$(aws cloudfront get-distribution --id $CLOUDFRONT_DIST_ID --profile $AWS_PROFILE --query 'Distribution.DomainName' --output text)"
