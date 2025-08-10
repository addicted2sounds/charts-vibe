#!/usr/bin/env python3
"""
Test script to verify SSM credentials setup
Run this after completing the migration to SSM Parameter Store
"""

import sys
import os

# Add the common directory to the path
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'common'))

try:
    from ssm_credentials import SSMCredentialsManager
    print("✅ Successfully imported SSMCredentialsManager")
except ImportError as e:
    print(f"❌ Failed to import SSMCredentialsManager: {e}")
    sys.exit(1)

def test_ssm_connection():
    """Test basic SSM connectivity"""
    try:
        manager = SSMCredentialsManager()
        if manager.test_connection():
            print("✅ SSM connection test passed")
            return True
        else:
            print("❌ SSM connection test failed - parameters may not exist")
            return False
    except Exception as e:
        print(f"❌ SSM connection error: {e}")
        return False

def test_credential_retrieval():
    """Test retrieving Google OAuth credentials"""
    try:
        manager = SSMCredentialsManager()
        config = manager.get_google_oauth_config()

        # Verify structure
        required_keys = ['client_id', 'client_secret', 'project_id', 'auth_uri', 'token_uri', 'auth_provider_x509_cert_url', 'redirect_uris']
        installed = config.get('installed', {})

        missing_keys = [key for key in required_keys if key not in installed]
        if missing_keys:
            print(f"❌ Missing required keys: {missing_keys}")
            return False

        # Check that sensitive data is not empty
        if not installed.get('client_id') or not installed.get('client_secret'):
            print("❌ Client ID or Client Secret is empty")
            return False

        print("✅ Successfully retrieved complete OAuth configuration")
        print(f"   Project ID: {installed['project_id']}")
        print(f"   Client ID: {installed['client_id'][:20]}...")
        print(f"   Redirect URIs: {installed['redirect_uris']}")
        return True

    except Exception as e:
        print(f"❌ Failed to retrieve credentials: {e}")
        return False

def test_individual_parameters():
    """Test retrieving individual parameters"""
    try:
        manager = SSMCredentialsManager()

        # Test non-sensitive parameter
        project_id = manager.get_parameter('project_id', decrypt=False)
        print(f"✅ Retrieved project_id: {project_id}")

        # Test sensitive parameter
        client_id = manager.get_parameter('client_id', decrypt=True)
        print(f"✅ Retrieved client_id: {client_id[:20]}...")

        return True

    except Exception as e:
        print(f"❌ Failed to retrieve individual parameters: {e}")
        return False

def test_file_absence():
    """Test that client_secret.json no longer exists"""
    client_secret_path = os.path.join(os.path.dirname(__file__), 'client_secret.json')
    if os.path.exists(client_secret_path):
        print(f"⚠️  WARNING: {client_secret_path} still exists!")
        print("   Run bin/cleanup-credentials.sh to remove it securely")
        return False
    else:
        print("✅ client_secret.json has been removed")
        return True

def main():
    print("Testing SSM Credentials Setup")
    print("=" * 40)

    tests = [
        ("SSM Connection", test_ssm_connection),
        ("Credential Retrieval", test_credential_retrieval),
        ("Individual Parameters", test_individual_parameters),
        ("File Absence", test_file_absence)
    ]

    results = []
    for test_name, test_func in tests:
        print(f"\n🔍 Running {test_name} test...")
        result = test_func()
        results.append((test_name, result))

    print("\n" + "=" * 40)
    print("TEST RESULTS")
    print("=" * 40)

    all_passed = True
    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} - {test_name}")
        if not passed:
            all_passed = False

    print("=" * 40)
    if all_passed:
        print("🎉 All tests passed! SSM credentials setup is working correctly.")
    else:
        print("⚠️  Some tests failed. Check the output above for details.")
        print("\nTroubleshooting:")
        print("1. Make sure you ran: ./bin/setup-ssm-parameters.sh")
        print("2. Check AWS credentials: aws sts get-caller-identity")
        print("3. Verify SSM parameters exist: aws ssm describe-parameters --parameter-filters \"Key=Name,Option=BeginsWith,Values=/ytmusic-playlist-app/\"")
        sys.exit(1)

if __name__ == "__main__":
    main()
