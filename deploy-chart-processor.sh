#!/bin/bash

# Deploy the Chart Processor Function
# This script helps deploy and test the chart processor function

set -e

echo "🚀 Deploying Chart Processor Function..."

# Build and deploy the SAM application
sam build
sam deploy --guided

echo "✅ Deployment completed!"

# Get the deployed resources
STACK_NAME=$(grep stack_name samconfig.toml | cut -d'"' -f2)
PLAYLISTS_BUCKET=$(aws cloudformation describe-stacks --stack-name $STACK_NAME --query 'Stacks[0].Outputs[?OutputKey==`PlaylistsBucketName`].OutputValue' --output text)
SNS_TOPIC_ARN=$(aws cloudformation describe-stacks --stack-name $STACK_NAME --query 'Stacks[0].Outputs[?OutputKey==`NewTracksTopicArn`].OutputValue' --output text)

echo "📦 Playlists Bucket: $PLAYLISTS_BUCKET"
echo "📨 SNS Topic ARN: $SNS_TOPIC_ARN"

# Test the function by uploading a sample chart
echo "🧪 Testing with sample chart..."

# Upload the sample chart to trigger the function
aws s3 cp chart-processor/sample_chart.json s3://$PLAYLISTS_BUCKET/test/sample_chart.json

echo "✅ Sample chart uploaded to trigger the function"
echo "📊 Check CloudWatch Logs for the ChartProcessorFunction to see the results"
echo "📨 Check SNS topic $SNS_TOPIC_ARN for published messages"

# Optional: Subscribe to SNS topic to see messages
read -p "Do you want to subscribe your email to receive SNS notifications? (y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    read -p "Enter your email address: " EMAIL
    aws sns subscribe --topic-arn $SNS_TOPIC_ARN --protocol email --notification-endpoint $EMAIL
    echo "📧 Check your email and confirm the subscription"
fi

echo "🎉 Setup completed!"
