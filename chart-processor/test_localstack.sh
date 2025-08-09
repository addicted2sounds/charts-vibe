#!/bin/bash

# Test Chart Processor with LocalStack using AWS CLI
# Make sure LocalStack is running on localhost:4566

echo "🎵 Testing Chart Processor with LocalStack"
echo "========================================="

# Set LocalStack endpoint
export AWS_ENDPOINT_URL="http://localhost:4566"
export AWS_DEFAULT_REGION="us-east-1"
export AWS_ACCESS_KEY_ID="test"
export AWS_SECRET_ACCESS_KEY="test"

echo "📋 Current LocalStack services status:"
curl -s http://localhost:4566/health | jq '.' || echo "LocalStack not running or jq not installed"

echo ""
echo "🔧 Setting up test resources..."

# Create S3 bucket
echo "Creating S3 bucket..."
aws s3 mb s3://charts-bucketa --endpoint-url=http://localhost:4566 2>/dev/null || echo "Bucket might already exist"

# Create DynamoDB table
echo "Creating DynamoDB table..."
aws dynamodb create-table \
    --table-name tracks \
    --attribute-definitions AttributeName=track_id,AttributeType=S \
    --key-schema AttributeName=track_id,KeyType=HASH \
    --billing-mode PAY_PER_REQUEST \
    --endpoint-url=http://localhost:4566 2>/dev/null || echo "Table might already exist"

# Create SNS topic
echo "Creating SNS topic..."
TOPIC_ARN=$(aws sns create-topic \
    --name new-tracks \
    --endpoint-url=http://localhost:4566 \
    --output text --query 'TopicArn' 2>/dev/null)

echo "Topic ARN: $TOPIC_ARN"

# Upload test chart data
echo "Uploading test chart data..."
aws s3 cp ../events/test-chart-data.json s3://charts-bucket/beatport/2024/08/09/top100-103000.json \
    --endpoint-url=http://localhost:4566 \
    --content-type=application/json

echo ""
echo "📊 Verifying setup..."

# List S3 objects
echo "S3 bucket contents:"
aws s3 ls s3://charts-bucket --recursive --endpoint-url=http://localhost:4566

# Check DynamoDB table
echo ""
echo "DynamoDB table description:"
aws dynamodb describe-table --table-name tracks --endpoint-url=http://localhost:4566 --query 'Table.[TableName,TableStatus]' --output table

echo ""
echo "🚀 To test the Lambda function, you can either:"
echo "1. Run the Python test script: python3 test_localstack.py"
echo "2. Manually invoke with AWS CLI:"
echo "   aws lambda invoke --function-name chart-processor --payload file://../events/chart-processor-event.json response.json --endpoint-url=http://localhost:4566"
echo ""
echo "✅ LocalStack setup complete!"

# Clean up function
cleanup() {
    echo ""
    echo "🧹 Cleaning up resources..."
    aws s3 rb s3://charts-bucket --force --endpoint-url=http://localhost:4566 2>/dev/null
    aws dynamodb delete-table --table-name tracks --endpoint-url=http://localhost:4566 2>/dev/null
    aws sns delete-topic --topic-arn "$TOPIC_ARN" --endpoint-url=http://localhost:4566 2>/dev/null
    echo "✅ Cleanup complete!"
}

# Ask if user wants to clean up
echo ""
read -p "Do you want to clean up the test resources? (y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    cleanup
fi
