#!/bin/bash

echo "🔒 Google OAuth2 Credentials Security Migration - Complete Setup Guide"
echo "====================================================================="
echo ""
echo "This script will guide you through the complete migration process."
echo "Follow these steps in order:"
echo ""

echo "📋 STEP 1: Prerequisites Check"
echo "------------------------------"

# Check AWS CLI
if command -v aws &> /dev/null; then
    echo "✅ AWS CLI is installed"
    if aws sts get-caller-identity &> /dev/null; then
        echo "✅ AWS credentials are configured"
    else
        echo "❌ AWS credentials not configured. Run: aws configure"
        exit 1
    fi
else
    echo "❌ AWS CLI not found. Please install AWS CLI first"
    exit 1
fi

# Check jq
if command -v jq &> /dev/null; then
    echo "✅ jq is installed"
else
    echo "❌ jq not found. Install with: brew install jq (macOS) or sudo apt-get install jq (Ubuntu)"
    exit 1
fi

# Check if client_secret.json exists
if [ -f "ytplaylist/client_secret.json" ]; then
    echo "✅ client_secret.json found"
else
    echo "❌ ytplaylist/client_secret.json not found"
    echo "   Please download OAuth2 credentials from Google Cloud Console first"
    exit 1
fi

echo ""
echo "🚀 STEP 2: Migrate credentials to SSM Parameter Store"
echo "------------------------------------------------------"
echo "This will store your Google OAuth2 credentials securely in AWS SSM..."
read -p "Continue? (y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    ./bin/setup-ssm-parameters.sh
else
    echo "Migration cancelled"
    exit 0
fi

echo ""
echo "🧪 STEP 3: Test SSM credentials"
echo "--------------------------------"
echo "Testing that credentials can be retrieved from SSM..."
./ytplaylist/test_ssm_credentials.py

if [ $? -ne 0 ]; then
    echo "❌ SSM test failed. Please check the output above"
    exit 1
fi

echo ""
echo "🔑 STEP 4: Complete OAuth flow and store tokens"
echo "------------------------------------------------"
echo "This will open a browser window for OAuth authorization..."
read -p "Continue with OAuth setup? (y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    cd ytplaylist
    python3 oauth_setup.py
    cd ..
else
    echo "OAuth setup skipped - you can run it later with: cd ytplaylist && python3 oauth_setup.py"
fi

echo ""
echo "🧹 STEP 5: Secure cleanup"
echo "--------------------------"
echo "⚠️  WARNING: This will remove client_secret.json and rewrite git history!"
echo "⚠️  All team members will need to re-clone the repository after this!"
echo ""
read -p "Proceed with secure cleanup? (yes/no): " -r
if [[ $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
    ./bin/cleanup-credentials.sh
else
    echo "Cleanup skipped. You can run it later with: ./bin/cleanup-credentials.sh"
    echo "⚠️  Remember to add ytplaylist/client_secret.json to .gitignore manually!"
fi

echo ""
echo "🎉 MIGRATION COMPLETED!"
echo "======================="
echo ""
echo "✅ Google OAuth2 credentials are now stored securely in AWS SSM Parameter Store"
echo "✅ Your application code has been updated to use SSM"
echo "✅ Sensitive files have been secured"
echo ""
echo "📝 Next steps:"
echo "1. If you ran cleanup, force push to remote: git push --force --all"
echo "2. Notify team members to re-clone the repository"
echo "3. Update your Lambda execution roles with SSM permissions (see SECURITY_README.md)"
echo "4. Deploy your updated application"
echo ""
echo "📚 Documentation:"
echo "- SECURITY_README.md - Quick start guide"
echo "- CREDENTIALS_MIGRATION.md - Detailed migration guide"
echo ""
echo "🔧 Useful commands:"
echo "- Test SSM: ./ytplaylist/test_ssm_credentials.py"
echo "- List parameters: aws ssm describe-parameters --parameter-filters \"Key=Name,Option=BeginsWith,Values=/ytmusic-playlist-app/\""
echo "- Re-run OAuth: cd ytplaylist && python3 oauth_setup.py"
