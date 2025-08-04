#!/bin/bash

# LocalStack deployment script
echo "Deploying to LocalStack..."

# Set LocalStack endpoint
export AWS_ENDPOINT_URL=http://localhost:4566
export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test
export AWS_DEFAULT_REGION=us-east-1

# Build and deploy with SAM
sam build --use-container
sam deploy \
  --resolve-s3 \
  --parameter-overrides ParameterKey=Environment,ParameterValue=local \
  --no-confirm-changeset

echo "Deployment complete!"

# Wait a moment for services to initialize
sleep 5

# Get the API Gateway endpoint
API_ENDPOINT=$(aws apigateway get-rest-apis --endpoint-url=http://localhost:4566 --query 'items[?name==`music-search-stack`].id' --output text)
if [ ! -z "$API_ENDPOINT" ]; then
    echo "API Gateway Endpoint: http://localhost:4566/restapis/$API_ENDPOINT/local/_user_request_"
else
    echo "API Gateway endpoint not found"
fi

# List DynamoDB tables
echo "DynamoDB Tables:"
aws dynamodb list-tables --endpoint-url=http://localhost:4566
