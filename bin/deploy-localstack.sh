#!/bin/bash

# LocalStack deployment script
echo "Deploying to LocalStack..."

# Set LocalStack endpoint
export AWS_ENDPOINT_URL=http://localhost:4566
export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test
export AWS_DEFAULT_REGION=us-east-1

CLEAN=false
if [[ "$1" == "--clean" ]]; then
    CLEAN=true
    shift
fi

if [[ "$CLEAN" == "true" ]]; then
    echo "Force cleaning existing stack..."
    aws cloudformation delete-stack --stack-name charts-vibe --endpoint-url=http://localhost:4566 --region us-east-1 2>/dev/null || true
    sleep 10
    echo "Waiting for stack deletion..."

fi

# Check if tables exist and set parameters accordingly
TABLES_EXIST=$(aws dynamodb list-tables --endpoint-url=http://localhost:4566 --region us-east-1 --query 'TableNames[?contains(@, `charts-vibe-jobs`)]' --output text 2>/dev/null)

if [ ! -z "$TABLES_EXIST" ]; then
    echo "Tables exist, using existing tables..."
    CREATE_TABLES="false"
else
    echo "Tables don't exist, creating new ones..."
    CREATE_TABLES="true"
fi

# Build and deploy with SAM
sam build #--use-container
sam deploy \
  --stack-name charts-vibe \
  --resolve-s3 \
  --no-confirm-changeset \
  --capabilities CAPABILITY_IAM \
  --region $AWS_DEFAULT_REGION \
  --parameter-overrides \
    CreateTables=$CREATE_TABLES \
    Environment=local

echo "Deployment complete!"

# Wait a moment for services to initialize
sleep 5

# List DynamoDB tables
echo "DynamoDB Tables:"
aws dynamodb list-tables --endpoint-url=http://localhost:4566 --region $AWS_DEFAULT_REGION
