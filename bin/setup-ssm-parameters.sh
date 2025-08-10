#!/bin/bash

# Script to set up SSM parameters from client_secret.json
# This script should be run once to migrate credentials to SSM Parameter Store

set -e

CLIENT_SECRET_FILE="ytplaylist/client_secret.json"
SSM_PREFIX="/ytmusic-playlist-app"

# Check if client_secret.json exists
if [ ! -f "$CLIENT_SECRET_FILE" ]; then
    echo "Error: $CLIENT_SECRET_FILE not found"
    exit 1
fi

# Check if jq is installed
if ! command -v jq &> /dev/null; then
    echo "Error: jq is required but not installed. Please install jq first."
    echo "On macOS: brew install jq"
    exit 1
fi

# Check if AWS CLI is configured
if ! aws sts get-caller-identity &> /dev/null; then
    echo "Error: AWS CLI is not configured or credentials are invalid"
    echo "Please run 'aws configure' first"
    exit 1
fi

echo "Setting up SSM parameters from $CLIENT_SECRET_FILE..."

# Extract values from JSON
CLIENT_ID=$(jq -r '.installed.client_id' "$CLIENT_SECRET_FILE")
PROJECT_ID=$(jq -r '.installed.project_id' "$CLIENT_SECRET_FILE")
AUTH_URI=$(jq -r '.installed.auth_uri' "$CLIENT_SECRET_FILE")
TOKEN_URI=$(jq -r '.installed.token_uri' "$CLIENT_SECRET_FILE")
AUTH_PROVIDER_CERT_URL=$(jq -r '.installed.auth_provider_x509_cert_url' "$CLIENT_SECRET_FILE")
CLIENT_SECRET=$(jq -r '.installed.client_secret' "$CLIENT_SECRET_FILE")
REDIRECT_URIS=$(jq -r '.installed.redirect_uris | join(",")' "$CLIENT_SECRET_FILE")

# Store sensitive parameters as SecureString
echo "Storing sensitive parameters..."
aws ssm put-parameter \
    --name "${SSM_PREFIX}/client_id" \
    --value "$CLIENT_ID" \
    --type "SecureString" \
    --description "Google OAuth2 Client ID for YT Music Playlist App" \
    --overwrite || echo "Warning: Failed to store client_id"

aws ssm put-parameter \
    --name "${SSM_PREFIX}/client_secret" \
    --value "$CLIENT_SECRET" \
    --type "SecureString" \
    --description "Google OAuth2 Client Secret for YT Music Playlist App" \
    --overwrite || echo "Warning: Failed to store client_secret"

# Store non-sensitive parameters as String
echo "Storing non-sensitive parameters..."
aws ssm put-parameter \
    --name "${SSM_PREFIX}/project_id" \
    --value "$PROJECT_ID" \
    --type "String" \
    --description "Google Cloud Project ID" \
    --overwrite || echo "Warning: Failed to store project_id"

aws ssm put-parameter \
    --name "${SSM_PREFIX}/auth_uri" \
    --value "$AUTH_URI" \
    --type "String" \
    --description "Google OAuth2 Authorization URI" \
    --overwrite || echo "Warning: Failed to store auth_uri"

aws ssm put-parameter \
    --name "${SSM_PREFIX}/token_uri" \
    --value "$TOKEN_URI" \
    --type "String" \
    --description "Google OAuth2 Token URI" \
    --overwrite || echo "Warning: Failed to store token_uri"

aws ssm put-parameter \
    --name "${SSM_PREFIX}/auth_provider_x509_cert_url" \
    --value "$AUTH_PROVIDER_CERT_URL" \
    --type "String" \
    --description "Google OAuth2 Certificate URL" \
    --overwrite || echo "Warning: Failed to store auth_provider_x509_cert_url"

aws ssm put-parameter \
    --name "${SSM_PREFIX}/redirect_uris" \
    --value "$REDIRECT_URIS" \
    --type "String" \
    --description "OAuth2 Redirect URIs (comma-separated)" \
    --overwrite || echo "Warning: Failed to store redirect_uris"

echo "✅ All parameters have been stored in SSM Parameter Store"
echo ""
echo "Parameters created:"
echo "- ${SSM_PREFIX}/client_id (SecureString)"
echo "- ${SSM_PREFIX}/client_secret (SecureString)"
echo "- ${SSM_PREFIX}/project_id (String)"
echo "- ${SSM_PREFIX}/auth_uri (String)"
echo "- ${SSM_PREFIX}/token_uri (String)"
echo "- ${SSM_PREFIX}/auth_provider_x509_cert_url (String)"
echo "- ${SSM_PREFIX}/redirect_uris (String)"
echo ""
echo "⚠️  IMPORTANT: Now you should:"
echo "1. Update your application code to read from SSM instead of the JSON file"
echo "2. Run the cleanup script to securely remove the client_secret.json file"
echo "3. Add ytplaylist/client_secret.json to .gitignore if not already present"
