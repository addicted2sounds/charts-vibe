#!/bin/bash

# Script to securely remove client_secret.json from repository and git history
# WARNING: This script will rewrite git history. Make sure all team members are aware.

set -e

CLIENT_SECRET_FILE="ytplaylist/client_secret.json"
GITIGNORE_FILE=".gitignore"

echo "🔒 Secure cleanup of client_secret.json from git repository"
echo "============================================================"

# Check if we're in a git repository
if [ ! -d ".git" ]; then
    echo "❌ Error: Not in a git repository"
    exit 1
fi

# Check if file exists
if [ ! -f "$CLIENT_SECRET_FILE" ]; then
    echo "ℹ️  File $CLIENT_SECRET_FILE doesn't exist in working directory"
else
    echo "📁 Found $CLIENT_SECRET_FILE in working directory"
fi

# Check if file is in git history
if git log --all --full-history -- "$CLIENT_SECRET_FILE" | grep -q "commit"; then
    echo "⚠️  File $CLIENT_SECRET_FILE found in git history"
    FOUND_IN_HISTORY=true
else
    echo "ℹ️  File $CLIENT_SECRET_FILE not found in git history"
    FOUND_IN_HISTORY=false
fi

# Confirm with user before proceeding
echo ""
echo "This script will:"
echo "1. Add $CLIENT_SECRET_FILE to .gitignore"
echo "2. Remove $CLIENT_SECRET_FILE from working directory (if exists)"
if [ "$FOUND_IN_HISTORY" = true ]; then
    echo "3. ⚠️  REWRITE GIT HISTORY to completely remove the file"
    echo ""
    echo "🚨 WARNING: This will rewrite git history!"
    echo "🚨 All team members will need to re-clone or force-pull the repository!"
    echo ""
fi
echo "4. Force garbage collection to ensure the file is completely removed"
echo ""

read -p "❓ Do you want to continue? (yes/no): " -r
if [[ ! $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
    echo "❌ Operation cancelled"
    exit 0
fi

# Step 1: Add to .gitignore
echo "📝 Adding $CLIENT_SECRET_FILE to .gitignore..."
if [ ! -f "$GITIGNORE_FILE" ]; then
    touch "$GITIGNORE_FILE"
fi

# Check if already in gitignore
if ! grep -Fxq "$CLIENT_SECRET_FILE" "$GITIGNORE_FILE"; then
    echo "" >> "$GITIGNORE_FILE"
    echo "# Google OAuth2 credentials - should be stored in SSM Parameter Store" >> "$GITIGNORE_FILE"
    echo "$CLIENT_SECRET_FILE" >> "$GITIGNORE_FILE"
    echo "✅ Added $CLIENT_SECRET_FILE to .gitignore"
else
    echo "ℹ️  $CLIENT_SECRET_FILE already in .gitignore"
fi

# Step 2: Remove from working directory
if [ -f "$CLIENT_SECRET_FILE" ]; then
    echo "🗑️  Removing $CLIENT_SECRET_FILE from working directory..."
    rm -f "$CLIENT_SECRET_FILE"
    echo "✅ Removed $CLIENT_SECRET_FILE from working directory"
fi

# Step 3: Remove from git history if found
if [ "$FOUND_IN_HISTORY" = true ]; then
    echo "🔄 Removing $CLIENT_SECRET_FILE from git history..."

    # Check if git filter-branch or git filter-repo is available
    if command -v git-filter-repo &> /dev/null; then
        echo "Using git-filter-repo (recommended method)..."
        git filter-repo --path "$CLIENT_SECRET_FILE" --invert-paths
    else
        echo "Using git filter-branch (fallback method)..."
        echo "📦 For better performance, consider installing git-filter-repo:"
        echo "   pip install git-filter-repo"

        git filter-branch --force --index-filter \
            "git rm --cached --ignore-unmatch $CLIENT_SECRET_FILE" \
            --prune-empty --tag-name-filter cat -- --all
    fi

    echo "✅ Removed $CLIENT_SECRET_FILE from git history"
fi

# Step 4: Clean up git
echo "🧹 Cleaning up git repository..."
git reflog expire --expire=now --all
git gc --prune=now --aggressive

echo "✅ Git cleanup completed"

# Stage .gitignore changes
if git diff --cached --quiet -- "$GITIGNORE_FILE"; then
    git add "$GITIGNORE_FILE"
    echo "✅ Staged .gitignore changes"
fi

echo ""
echo "🎉 Cleanup completed successfully!"
echo ""
echo "📋 Next steps:"
echo "1. Commit the .gitignore changes:"
echo "   git commit -m \"Add client_secret.json to .gitignore and remove from history\""
echo ""

if [ "$FOUND_IN_HISTORY" = true ]; then
    echo "2. ⚠️  IMPORTANT: Force push to update remote repository:"
    echo "   git push --force --all"
    echo "   git push --force --tags"
    echo ""
    echo "3. 🚨 Notify all team members to:"
    echo "   - Save their local changes"
    echo "   - Delete their local repository"
    echo "   - Re-clone the repository"
    echo "   OR use: git pull --force"
    echo ""
fi

echo "4. Verify the file is completely removed:"
echo "   git log --all --full-history -- $CLIENT_SECRET_FILE"
echo "   (should return no results)"
echo ""
echo "5. Make sure SSM parameters are set up before deploying:"
echo "   ./bin/setup-ssm-parameters.sh"
