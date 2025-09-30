import * as cdk from 'aws-cdk-lib';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as cloudfront from 'aws-cdk-lib/aws-cloudfront';
import * as origins from 'aws-cdk-lib/aws-cloudfront-origins';
import * as s3deploy from 'aws-cdk-lib/aws-s3-deployment';
import * as route53 from 'aws-cdk-lib/aws-route53';
import * as targets from 'aws-cdk-lib/aws-route53-targets';
import * as acm from 'aws-cdk-lib/aws-certificatemanager';
import { Construct } from 'constructs';

export interface RagFrontendStackProps extends cdk.StackProps {
  apiUrl: string;
  domainName?: string;
  certificateArn?: string;
}

export class RagFrontendStack extends cdk.Stack {
  public readonly frontendBucket: s3.Bucket;
  public readonly distribution: cloudfront.Distribution;

  constructor(scope: Construct, id: string, props: RagFrontendStackProps) {
    super(scope, id, props);

    // Create S3 bucket for frontend hosting
    this.frontendBucket = new s3.Bucket(this, 'RagFrontendBucket', {
      bucketName: `${props.domainName?.replace('.', '-')}-rag-frontend`,
      websiteIndexDocument: 'index.html',
      websiteErrorDocument: 'error.html',
      publicReadAccess: false, // CloudFront will handle access
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      encryption: s3.BucketEncryption.S3_MANAGED,
      removalPolicy: cdk.RemovalPolicy.RETAIN,
      cors: [
        {
          allowedMethods: [s3.HttpMethods.GET, s3.HttpMethods.HEAD],
          allowedOrigins: ['*'],
          allowedHeaders: ['*'],
          maxAge: 3600,
        },
      ],
    });

    // Create Origin Access Identity for CloudFront
    const oai = new cloudfront.OriginAccessIdentity(this, 'RagFrontendOAI', {
      comment: 'OAI for Dontron Blog RAG Frontend',
    });

    // Grant CloudFront access to S3
    this.frontendBucket.grantRead(oai);

    // Configure CloudFront cache behaviors
    const apiCacheBehavior: cloudfront.BehaviorOptions = {
      origin: new origins.HttpOrigin(props.apiUrl.replace('https://', '').replace('http://', ''), {
        protocolPolicy: cloudfront.OriginProtocolPolicy.HTTPS_ONLY,
      }),
      allowedMethods: cloudfront.AllowedMethods.ALLOW_ALL,
      cachePolicy: cloudfront.CachePolicy.CACHING_DISABLED,
      originRequestPolicy: cloudfront.OriginRequestPolicy.ALL_VIEWER_EXCEPT_HOST_HEADER,
      viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
    };

    // Certificate for custom domain (if provided)
    const certificate = props.certificateArn
      ? acm.Certificate.fromCertificateArn(this, 'Certificate', props.certificateArn)
      : undefined;

    // Create CloudFront distribution
    this.distribution = new cloudfront.Distribution(this, 'RagFrontendDistribution', {
      defaultBehavior: {
        origin: new origins.S3Origin(this.frontendBucket, {
          originAccessIdentity: oai,
        }),
        viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
        cachePolicy: cloudfront.CachePolicy.CACHING_OPTIMIZED,
        compress: true,
        allowedMethods: cloudfront.AllowedMethods.ALLOW_GET_HEAD_OPTIONS,
      },
      additionalBehaviors: {
        '/api/*': apiCacheBehavior,
      },
      domainNames: props.domainName ? [`rag.${props.domainName}`] : undefined,
      certificate,
      defaultRootObject: 'index.html',
      errorResponses: [
        {
          httpStatus: 404,
          responseHttpStatus: 200,
          responsePagePath: '/index.html',
          ttl: cdk.Duration.minutes(5),
        },
        {
          httpStatus: 403,
          responseHttpStatus: 200,
          responsePagePath: '/index.html',
          ttl: cdk.Duration.minutes(5),
        },
      ],
      priceClass: cloudfront.PriceClass.PRICE_CLASS_100,
      enabled: true,
      comment: 'Dontron Blog RAG Frontend Distribution',
    });

    // Deploy frontend files
    new s3deploy.BucketDeployment(this, 'DeployRagFrontend', {
      sources: [s3deploy.Source.asset('../rag-frontend/build')],
      destinationBucket: this.frontendBucket,
      distribution: this.distribution,
      distributionPaths: ['/*'],
      prune: true,
      memoryLimit: 512,
    });

    // Create Route53 record (if custom domain)
    if (props.domainName) {
      const hostedZone = route53.HostedZone.fromLookup(this, 'HostedZone', {
        domainName: props.domainName,
      });

      new route53.ARecord(this, 'RagFrontendARecord', {
        zone: hostedZone,
        recordName: `rag.${props.domainName}`,
        target: route53.RecordTarget.fromAlias(
          new targets.CloudFrontTarget(this.distribution)
        ),
      });

      new route53.AaaaRecord(this, 'RagFrontendAAAARecord', {
        zone: hostedZone,
        recordName: `rag.${props.domainName}`,
        target: route53.RecordTarget.fromAlias(
          new targets.CloudFrontTarget(this.distribution)
        ),
      });
    }

    // Outputs
    new cdk.CfnOutput(this, 'FrontendUrl', {
      value: props.domainName
        ? `https://rag.${props.domainName}`
        : `https://${this.distribution.distributionDomainName}`,
      description: 'RAG Frontend URL',
      exportName: 'RagFrontendUrl',
    });

    new cdk.CfnOutput(this, 'FrontendBucketName', {
      value: this.frontendBucket.bucketName,
      description: 'S3 bucket for RAG frontend',
      exportName: 'RagFrontendBucketName',
    });

    new cdk.CfnOutput(this, 'CloudFrontDistributionId', {
      value: this.distribution.distributionId,
      description: 'CloudFront Distribution ID',
      exportName: 'RagCloudFrontDistributionId',
    });
  }
}