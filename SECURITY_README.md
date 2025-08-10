# 🔒 Google OAuth2 Credentials Security Migration

This project has been migrated to use AWS Systems Manager Parameter Store for secure credential storage instead of storing sensitive information in `client_secret.json` files.

## 🚀 Quick Start (For New Setups)

1. **Install dependencies:**
   ```bash
   pip install boto3 jq
   # On macOS: brew install jq
   ```

2. **Set up your `client_secret.json` temporarily:**
   - Download OAuth2 credentials from Google Cloud Console
   - Place in `ytplaylist/client_secret.json`

3. **Run the migration:**
   ```bash
   # Store credentials in SSM Parameter Store
   ./bin/setup-ssm-parameters.sh
   
   # Test the setup
   ./ytplaylist/test_ssm_credentials.py
   
   # Complete OAuth flow and store tokens
   cd ytplaylist && python3 oauth_setup.py
   
   # Securely remove the file and clean git history
   ./bin/cleanup-credentials.sh
   ```

4. **Commit and push:**
   ```bash
   git commit -m "Migrate to SSM Parameter Store for credentials"
   git push --force --all  # Required after history cleanup
   ```

## 📋 Migration Checklist

- [ ] AWS CLI configured with SSM permissions
- [ ] `jq` installed for JSON processing
- [ ] Run `./bin/setup-ssm-parameters.sh`
- [ ] Verify with `./ytplaylist/test_ssm_credentials.py`
- [ ] Complete OAuth with `oauth_setup.py`
- [ ] Run `./bin/cleanup-credentials.sh`
- [ ] Force push to remote: `git push --force --all`
- [ ] Notify team members to re-clone

## 🔑 SSM Parameters Created

### Sensitive (SecureString)
- `/ytmusic-playlist-app/client_id`
- `/ytmusic-playlist-app/client_secret`
- `/youtube/access_token`
- `/youtube/refresh_token`

### Non-Sensitive (String)
- `/ytmusic-playlist-app/project_id`
- `/ytmusic-playlist-app/auth_uri`
- `/ytmusic-playlist-app/token_uri`
- `/ytmusic-playlist-app/auth_provider_x509_cert_url`
- `/ytmusic-playlist-app/redirect_uris`

## 🛠 Code Usage

```python
from common.ssm_credentials import SSMCredentialsManager

# Get Google OAuth2 config
manager = SSMCredentialsManager()
config = manager.get_google_oauth_config()

# Use like the old client_secret.json format
client_id = config['installed']['client_id']
client_secret = config['installed']['client_secret']
```

## 🔧 Required AWS Permissions

Your AWS credentials need these SSM permissions:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "ssm:GetParameter",
                "ssm:GetParameters",
                "ssm:PutParameter"
            ],
            "Resource": [
                "arn:aws:ssm:*:*:parameter/ytmusic-playlist-app/*",
                "arn:aws:ssm:*:*:parameter/youtube/*"
            ]
        }
    ]
}
```

## 🚨 Security Benefits

- ✅ **No secrets in git** - Credentials never stored in source code
- ✅ **Encrypted at rest** - SSM SecureString uses KMS encryption  
- ✅ **Access control** - IAM controls parameter access
- ✅ **Audit trail** - CloudTrail logs all access
- ✅ **Easy rotation** - Update parameters without code changes

## 🧪 Testing

```bash
# Test SSM setup
./ytplaylist/test_ssm_credentials.py

# Verify git history is clean
git log --all --full-history -- ytplaylist/client_secret.json
# Should return no results

# List SSM parameters
aws ssm describe-parameters --parameter-filters "Key=Name,Option=BeginsWith,Values=/ytmusic-playlist-app/"
```

## 🆘 Troubleshooting

### AWS Not Configured
```bash
aws configure
# or set AWS_PROFILE environment variable
```

### Missing jq
```bash
# macOS
brew install jq

# Ubuntu/Debian  
sudo apt-get install jq

# CentOS/RHEL
sudo yum install jq
```

### SSM Parameters Not Found
```bash
# Check parameters exist
aws ssm describe-parameters --parameter-filters "Key=Name,Option=BeginsWith,Values=/ytmusic-playlist-app/"

# Re-run setup if needed
./bin/setup-ssm-parameters.sh
```

### Git History Still Shows Secrets
```bash
# Force cleanup
git filter-branch --force --index-filter \
    "git rm --cached --ignore-unmatch ytplaylist/client_secret.json" \
    --prune-empty --tag-name-filter cat -- --all
git reflog expire --expire=now --all  
git gc --prune=now --aggressive
```

## 📚 Additional Resources

- [AWS SSM Parameter Store Documentation](https://docs.aws.amazon.com/systems-manager/latest/userguide/systems-manager-parameter-store.html)
- [Google OAuth2 Setup Guide](https://developers.google.com/identity/protocols/oauth2)
- [Full Migration Guide](./CREDENTIALS_MIGRATION.md)

---
**⚠️ Important**: After running cleanup scripts, all team members must re-clone the repository since git history has been rewritten.
