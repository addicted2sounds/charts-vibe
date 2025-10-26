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

if [ -z "$AWS_REGION" ]; then
    echo "Error: AWS region is not configured. Please set it with 'aws configure set region <region-name>'"
    exit 1
fi

# Ensure we're in the project root
cd "$(dirname "$0")/.."

# Table names (override with env vars if needed)
TRACKS_TABLE_NAME=${TRACKS_TABLE_NAME:-charts-vibe-tracks}
PLAYLISTS_TABLE_NAME=${PLAYLISTS_TABLE_NAME:-charts-vibe-playlists}
JOBS_TABLE_NAME=${JOBS_TABLE_NAME:-charts-vibe-jobs}

# Ensure we have an S3 bucket for SAM artifacts. Allow override via SAM_ARTIFACT_BUCKET.
SAM_ARTIFACT_BUCKET=${SAM_ARTIFACT_BUCKET:-charts-vibe-sam-artifacts-$AWS_ACCOUNT_ID-$AWS_REGION}
echo "Using SAM artifact bucket: $SAM_ARTIFACT_BUCKET"

if ! aws s3api head-bucket --bucket "$SAM_ARTIFACT_BUCKET" 2>/dev/null; then
    echo "Artifact bucket does not exist. Creating s3://$SAM_ARTIFACT_BUCKET ..."
    if [ "$AWS_REGION" = "us-east-1" ]; then
        aws s3api create-bucket --bucket "$SAM_ARTIFACT_BUCKET"
    else
        aws s3api create-bucket \
            --bucket "$SAM_ARTIFACT_BUCKET" \
            --create-bucket-configuration LocationConstraint="$AWS_REGION"
    fi
fi

# Determine if DynamoDB tables already exist
CREATE_TABLES=true
if aws dynamodb describe-table --table-name "$TRACKS_TABLE_NAME" --region "$AWS_REGION" >/dev/null 2>&1 \
   && aws dynamodb describe-table --table-name "$PLAYLISTS_TABLE_NAME" --region "$AWS_REGION" >/dev/null 2>&1 \
   && aws dynamodb describe-table --table-name "$JOBS_TABLE_NAME" --region "$AWS_REGION" >/dev/null 2>&1; then
    CREATE_TABLES=false
fi

echo "DynamoDB tables check:"
if [ "$CREATE_TABLES" = true ]; then
    echo "  Tables missing - will create new DynamoDB tables."
else
    echo "  Existing tables detected - reusing $TRACKS_TABLE_NAME, $PLAYLISTS_TABLE_NAME, $JOBS_TABLE_NAME."
fi

echo "########### Building SAM application ###########"
sam build

echo "########### Deploying to AWS ###########"
sam deploy \
    --config-env default \
    --s3-bucket "$SAM_ARTIFACT_BUCKET" \
    --capabilities CAPABILITY_IAM \
    --parameter-overrides \
        Environment=production \
        CreateTables=$CREATE_TABLES \
        ExistingTracksTableName=$TRACKS_TABLE_NAME \
        ExistingPlaylistsTableName=$PLAYLISTS_TABLE_NAME \
        ExistingJobsTableName=$JOBS_TABLE_NAME

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
