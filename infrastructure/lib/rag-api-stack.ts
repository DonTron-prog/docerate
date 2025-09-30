import * as cdk from 'aws-cdk-lib';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as apigateway from 'aws-cdk-lib/aws-apigateway';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as logs from 'aws-cdk-lib/aws-logs';
import * as route53 from 'aws-cdk-lib/aws-route53';
import * as targets from 'aws-cdk-lib/aws-route53-targets';
import * as acm from 'aws-cdk-lib/aws-certificatemanager';
import { Construct } from 'constructs';

export interface RagApiStackProps extends cdk.StackProps {
  domainName?: string;
  certificateArn?: string;
}

export class RagApiStack extends cdk.Stack {
  public readonly apiUrl: string;
  public readonly ragDataBucket: s3.Bucket;
  public readonly lambdaFunction: lambda.Function;

  constructor(scope: Construct, id: string, props?: RagApiStackProps) {
    super(scope, id, props);

    // Create S3 bucket for RAG data (indexes, embeddings)
    this.ragDataBucket = new s3.Bucket(this, 'RagDataBucket', {
      bucketName: `${props?.domainName?.replace('.', '-')}-rag-data`,
      versioned: true,
      encryption: s3.BucketEncryption.S3_MANAGED,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      lifecycleRules: [
        {
          id: 'DeleteOldVersions',
          noncurrentVersionExpiration: cdk.Duration.days(30),
        },
      ],
      removalPolicy: cdk.RemovalPolicy.RETAIN,
    });

    // Create Lambda layer for dependencies (optional - for large dependencies)
    const dependenciesLayer = new lambda.LayerVersion(this, 'RagDependencies', {
      code: lambda.Code.fromAsset('../lambda-layer-dependencies.zip', {
        exclude: ['*.pyc', '__pycache__'],
      }),
      compatibleRuntimes: [lambda.Runtime.PYTHON_3_11],
      description: 'RAG system dependencies',
    });

    // Create Lambda function for RAG API
    this.lambdaFunction = new lambda.Function(this, 'RagApiFunction', {
      functionName: 'dontron-blog-rag-api',
      runtime: lambda.Runtime.PYTHON_3_11,
      handler: 'backend.lambda_handler.handler',
      code: lambda.Code.fromAsset('../lambda-package.zip', {
        exclude: ['*.pyc', '__pycache__', 'tests/', '.env'],
      }),
      memorySize: 2048, // Increase for better performance
      timeout: cdk.Duration.seconds(60), // API Gateway has a 30s limit, but direct invoke can use 60s
      environment: {
        RAG_DATA_BUCKET: this.ragDataBucket.bucketName,
        USE_BEDROCK: 'true',
        BEDROCK_MODEL_ID: 'anthropic.claude-3-sonnet-20240229-v1:0',
        EMBEDDING_MODEL: 'amazon.titan-embed-text-v1',
        PYTHONPATH: '/var/task:/opt/python',
      },
      layers: [dependenciesLayer],
      logRetention: logs.RetentionDays.ONE_WEEK,
      tracing: lambda.Tracing.ACTIVE,
    });

    // Grant Lambda permissions to read from S3
    this.ragDataBucket.grantRead(this.lambdaFunction);

    // Grant Lambda permissions to use Bedrock
    this.lambdaFunction.addToRolePolicy(
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        actions: [
          'bedrock:InvokeModel',
          'bedrock:InvokeModelWithResponseStream',
        ],
        resources: [
          `arn:aws:bedrock:${this.region}::foundation-model/*`,
        ],
      })
    );

    // Create API Gateway
    const api = new apigateway.RestApi(this, 'RagApi', {
      restApiName: 'Dontron Blog RAG API',
      description: 'API for RAG-powered article generation',
      deployOptions: {
        stageName: 'prod',
        tracingEnabled: true,
        dataTraceEnabled: true,
        loggingLevel: apigateway.MethodLoggingLevel.INFO,
        metricsEnabled: true,
        throttlingBurstLimit: 100,
        throttlingRateLimit: 50,
      },
      defaultCorsPreflightOptions: {
        allowOrigins: apigateway.Cors.ALL_ORIGINS,
        allowMethods: apigateway.Cors.ALL_METHODS,
        allowHeaders: [
          'Content-Type',
          'X-Amz-Date',
          'Authorization',
          'X-Api-Key',
          'X-Amz-Security-Token',
        ],
      },
    });

    // Create Lambda integration
    const lambdaIntegration = new apigateway.LambdaIntegration(this.lambdaFunction, {
      requestTemplates: { 'application/json': '{ "statusCode": "200" }' },
    });

    // Add routes
    const apiResource = api.root.addResource('api');

    // Health check
    const health = apiResource.addResource('health');
    health.addMethod('GET', lambdaIntegration);

    // Tags endpoint
    const tags = apiResource.addResource('tags');
    tags.addMethod('GET', lambdaIntegration);

    // Search endpoint
    const search = apiResource.addResource('search');
    search.addMethod('POST', lambdaIntegration);

    // Generate endpoint
    const generate = apiResource.addResource('generate');
    generate.addMethod('POST', lambdaIntegration);

    // Generate stream endpoint
    const generateStream = generate.addResource('stream');
    generateStream.addMethod('GET', lambdaIntegration);

    // Custom domain (optional)
    if (props?.domainName && props?.certificateArn) {
      const certificate = acm.Certificate.fromCertificateArn(
        this,
        'Certificate',
        props.certificateArn
      );

      const domainName = new apigateway.DomainName(this, 'RagApiDomain', {
        domainName: `rag-api.${props.domainName}`,
        certificate,
        endpointType: apigateway.EndpointType.EDGE,
        securityPolicy: apigateway.SecurityPolicy.TLS_1_2,
      });

      domainName.addBasePathMapping(api, {
        basePath: '',
      });

      // Create Route53 record
      const hostedZone = route53.HostedZone.fromLookup(this, 'HostedZone', {
        domainName: props.domainName,
      });

      new route53.ARecord(this, 'RagApiARecord', {
        zone: hostedZone,
        recordName: `rag-api.${props.domainName}`,
        target: route53.RecordTarget.fromAlias(
          new targets.ApiGatewayDomain(domainName)
        ),
      });

      this.apiUrl = `https://rag-api.${props.domainName}`;
    } else {
      this.apiUrl = api.url;
    }

    // Output the API URL
    new cdk.CfnOutput(this, 'ApiUrl', {
      value: this.apiUrl,
      description: 'RAG API URL',
      exportName: 'RagApiUrl',
    });

    // Output the S3 bucket name
    new cdk.CfnOutput(this, 'RagDataBucketName', {
      value: this.ragDataBucket.bucketName,
      description: 'S3 bucket for RAG data',
      exportName: 'RagDataBucketName',
    });
  }
}