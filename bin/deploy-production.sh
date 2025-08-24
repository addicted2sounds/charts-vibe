#!/bin/bash

# Production deployment script for charts-vibe AWS infrastructure
# This script deploys the enhanced S3 events configuration to AWS

set -e  # Exit on error

echo "########### Charts-vibe Production Deployment ###########"

# Check if AWS CLI is configured
if ! aws sts get-caller-identity > /dev/null 2>&1; then
    echo "Error: AWS CLI not configured or no valid credentials found"
    echo "Please run 'aws configure' or set up your AWS credentials"
    exit 1
fi

# Get current AWS region and account info
export AWS_REGION=$(aws configure get region)
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
echo "Deploying to AWS Account: $AWS_ACCOUNT_ID"
echo "AWS Region: $AWS_REGION"

# Ensure we're in the project root
cd "$(dirname "$0")/.."

echo "########### Building SAM application ###########"
sam build

echo "########### Deploying to AWS ###########"
sam deploy --config-env default

echo "########### Getting stack outputs ###########"
STACK_NAME="charts-vibe"

# Get important outputs
PLAYLISTS_BUCKET=$(aws cloudformation describe-stacks \
    --stack-name $STACK_NAME \
    --query 'Stacks[0].Outputs[?OutputKey==`PlaylistsBucketName`].OutputValue' \
    --output text)

S3_UPLOAD_QUEUE_URL=$(aws cloudformation describe-stacks \
    --stack-name $STACK_NAME \
    --query 'Stacks[0].Outputs[?OutputKey==`S3FileUploadQueueUrl`].OutputValue' \
    --output text)

echo "########### Deployment Summary ###########"
echo "Stack Name: $STACK_NAME"
echo "Playlists Bucket: $PLAYLISTS_BUCKET"
echo "S3 Upload Events Queue: $S3_UPLOAD_QUEUE_URL"

echo "########### Testing S3 bucket notification configuration ###########"
aws s3api get-bucket-notification-configuration --bucket $PLAYLISTS_BUCKET

echo "########### Listing SQS queues ###########"
aws sqs list-queues --queue-name-prefix $STACK_NAME

echo "########### Deployment completed successfully! ###########"
echo ""
echo "Your S3 bucket is now configured to:"
echo "- Send upload events to: $S3_UPLOAD_QUEUE_URL"
echo "- Process events through Lambda functions via SQS"
echo ""
echo "To test the setup:"
echo "1. Upload a .json file to: s3://$PLAYLISTS_BUCKET/"
echo "2. Check CloudWatch logs for the ChartProcessorFunction"
