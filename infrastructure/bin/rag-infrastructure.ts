#!/usr/bin/env node
import 'source-map-support/register';
import * as cdk from 'aws-cdk-lib';
import { RagApiStack } from '../lib/rag-api-stack';
import { RagFrontendStack } from '../lib/rag-frontend-stack';

const app = new cdk.App();

// Get configuration from context or use defaults
const env = {
  account: process.env.CDK_DEFAULT_ACCOUNT,
  region: process.env.CDK_DEFAULT_REGION || 'us-east-1',
};

const domainName = app.node.tryGetContext('domainName') || 'donaldmcgillivray.com';
const certificateArn = app.node.tryGetContext('certificateArn');

// Deploy the RAG API backend (Lambda + API Gateway)
const ragApiStack = new RagApiStack(app, 'DontronBlogRagApiStack', {
  env,
  description: 'Dontron Blog RAG API - Lambda functions and API Gateway',
  domainName,
  certificateArn,
});

// Deploy the RAG Frontend (S3 + CloudFront)
const ragFrontendStack = new RagFrontendStack(app, 'DontronBlogRagFrontendStack', {
  env,
  description: 'Dontron Blog RAG Frontend - S3 and CloudFront distribution',
  apiUrl: ragApiStack.apiUrl,
  domainName,
  certificateArn,
});

// Add dependency
ragFrontendStack.addDependency(ragApiStack);

// Add tags to all resources
cdk.Tags.of(app).add('Project', 'DontronBlog');
cdk.Tags.of(app).add('Component', 'RAG');
cdk.Tags.of(app).add('Environment', 'Production');