# Google OAuth2 Credentials Migration Guide

This guide explains how to securely migrate Google OAuth2 credentials from `client_secret.json` file to AWS Systems Manager Parameter Store.

## Overview

Instead of storing sensitive credentials in a JSON file that could accidentally be committed to git, we now store:
- **Sensitive data** (`client_id`, `client_secret`) as **SecureString** parameters in SSM
- **Non-sensitive data** (URLs, project_id) as regular **String** parameters in SSM

## Migration Steps

### 1. Prerequisites

Make sure you have:
- AWS CLI configured with appropriate permissions
- `jq` installed (`brew install jq` on macOS)
- SSM permissions: `ssm:GetParameter`, `ssm:PutParameter`

### 2. Set up SSM Parameters

Run the setup script to migrate credentials from `client_secret.json` to SSM Parameter Store:

```bash
./bin/setup-ssm-parameters.sh
```

This script will:
- Read credentials from `ytplaylist/client_secret.json`
- Store `client_id` and `client_secret` as SecureString parameters
- Store other configuration as regular String parameters
- Create parameters under `/ytmusic-playlist-app/` prefix

### 3. Verify SSM Parameters

Test that the credentials can be read from SSM:

```bash
# Test the credentials manager
python3 common/ssm_credentials.py
```

You should see output confirming successful retrieval of credentials.

### 4. Complete OAuth Setup

Run the OAuth setup to store access tokens:

```bash
cd ytplaylist
python3 oauth_setup.py
```

This will:
- Read client credentials from SSM Parameter Store
- Complete OAuth flow in browser
- Store access/refresh tokens in SSM as SecureStrings

### 5. Remove Sensitive Files

**⚠️ WARNING: This step will rewrite git history!**

Run the cleanup script to securely remove `client_secret.json`:

```bash
./bin/cleanup-credentials.sh
```

This script will:
- Add `client_secret.json` to `.gitignore`
- Remove the file from working directory
- Remove the file from git history completely
- Force garbage collection

### 6. Update Remote Repository

After cleanup, you need to force push to update the remote repository:

```bash
git push --force --all
git push --force --tags
```

**Important**: All team members must re-clone the repository or force pull!

## SSM Parameter Structure

The following parameters are created in SSM Parameter Store:

### Sensitive Parameters (SecureString)
- `/ytmusic-playlist-app/client_id`
- `/ytmusic-playlist-app/client_secret`
- `/youtube/access_token`
- `/youtube/refresh_token`

### Non-Sensitive Parameters (String)
- `/ytmusic-playlist-app/project_id`
- `/ytmusic-playlist-app/auth_uri`
- `/ytmusic-playlist-app/token_uri`
- `/ytmusic-playlist-app/auth_provider_x509_cert_url`
- `/ytmusic-playlist-app/redirect_uris`

## Code Changes

The application code has been updated to use `SSMCredentialsManager` from `common/ssm_credentials.py`:

```python
from common.ssm_credentials import SSMCredentialsManager

# Get Google OAuth config from SSM
ssm_manager = SSMCredentialsManager()
config = ssm_manager.get_google_oauth_config()
```

## Testing

### Local Testing

```bash
# Test SSM credentials manager
python3 common/ssm_credentials.py

# Test ytplaylist OAuth setup
cd ytplaylist
python3 oauth_setup.py
```

### Verify Git History

Confirm the sensitive file is completely removed:

```bash
git log --all --full-history -- ytplaylist/client_secret.json
```

This should return no results.

## Security Benefits

1. **No secrets in code**: Credentials are never stored in source code
2. **Encrypted at rest**: SSM SecureString parameters are encrypted with KMS
3. **Access control**: IAM controls who can read parameters
4. **Audit trail**: CloudTrail logs all parameter access
5. **Rotation**: Tokens can be rotated without code changes

## Troubleshooting

### AWS Credentials Not Configured
```bash
aws configure
# or
export AWS_PROFILE=your-profile
```

### SSM Parameters Not Found
```bash
# List all parameters under our prefix
aws ssm describe-parameters --parameter-filters "Key=Name,Option=BeginsWith,Values=/ytmusic-playlist-app/"
```

### Git History Still Shows File
```bash
# Force cleanup if needed
git filter-branch --force --index-filter \
    "git rm --cached --ignore-unmatch ytplaylist/client_secret.json" \
    --prune-empty --tag-name-filter cat -- --all
git reflog expire --expire=now --all
git gc --prune=now --aggressive
```

## Production Deployment

For Lambda deployments, ensure the execution role has SSM permissions:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "ssm:GetParameter",
                "ssm:GetParameters"
            ],
            "Resource": [
                "arn:aws:ssm:*:*:parameter/ytmusic-playlist-app/*",
                "arn:aws:ssm:*:*:parameter/youtube/*"
            ]
        }
    ]
}
```
