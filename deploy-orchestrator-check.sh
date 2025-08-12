#!/bin/bash

echo "=== Simple Orchestrator Deployment Check ==="
echo "Checking template.yaml validity and readiness for deployment"
echo ""

# Check if sam CLI is available
if ! command -v sam &> /dev/null; then
    echo "❌ SAM CLI not found. Please install AWS SAM CLI first."
    exit 1
fi

# Check template syntax
echo "🔍 Validating CloudFormation template..."
sam validate --template template.yaml

if [ $? -eq 0 ]; then
    echo "✅ Template validation passed"
else
    echo "❌ Template validation failed"
    exit 1
fi

echo ""
echo "📋 Orchestrator Components Summary:"
echo "├── Jobs Table: tracks expected_count vs processed_count"
echo "├── ChartProcessor: creates job records, publishes with job_id"
echo "├── YoutubeMusicSearch: updates counters, sends completion events"
echo "├── YoutubePlaylist: auto-triggered by EventBridge on job completion"
echo "└── EventBridge: orchestrates job completion → playlist creation"

echo ""
echo "🚀 Ready for deployment:"
echo "   sam build && sam deploy"

echo ""
echo "📊 After deployment, monitor with:"
echo "   aws dynamodb scan --table-name \$(SAM_STACK_NAME)-jobs"
echo "   aws logs tail /aws/lambda/\$(SAM_STACK_NAME)-YoutubeMusicSearchFunction --follow"

echo ""
echo "🧪 Test the orchestrator:"
echo "   curl \"https://\$(API_ENDPOINT)/Prod/scrape\""
echo "   # This will trigger: scraper → S3 → chart processor → job creation → track processing → auto playlist"

echo ""
echo "✨ Simple orchestrator setup complete!"
