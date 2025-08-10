#!/usr/bin/env python3
"""
Test script to invoke the chart processor Lambda function on LocalStack
"""

import json
import boto3
import os
import sys

def setup_localstack_resources():
    """Setup the required AWS resources in LocalStack"""

    # Configure boto3 to use LocalStack
    endpoint_url = 'http://localhost:4566'

    # Create AWS clients
    s3_client = boto3.client('s3', endpoint_url=endpoint_url, region_name='us-east-1')
    dynamodb = boto3.resource('dynamodb', endpoint_url=endpoint_url, region_name='us-east-1')
    sns_client = boto3.client('sns', endpoint_url=endpoint_url, region_name='us-east-1')
    lambda_client = boto3.client('lambda', endpoint_url=endpoint_url, region_name='us-east-1')

    print("🔧 Setting up LocalStack resources...")

    # 1. Create S3 bucket for charts
    bucket_name = 'charts-bucket'
    try:
        s3_client.create_bucket(Bucket=bucket_name)
        print(f"✅ Created S3 bucket: {bucket_name}")
    except s3_client.exceptions.BucketAlreadyOwnedByYou:
        print(f"✅ S3 bucket already exists: {bucket_name}")
    except Exception as e:
        print(f"❌ Error creating S3 bucket: {e}")
        return False

    # 2. Create DynamoDB tracks table
    table_name = 'tracks'
    try:
        table = dynamodb.create_table(
            TableName=table_name,
            KeySchema=[
                {'AttributeName': 'track_id', 'KeyType': 'HASH'}
            ],
            AttributeDefinitions=[
                {'AttributeName': 'track_id', 'AttributeType': 'S'}
            ],
            BillingMode='PAY_PER_REQUEST'
        )
        print(f"✅ Created DynamoDB table: {table_name}")
    except dynamodb.meta.client.exceptions.ResourceInUseException:
        print(f"✅ DynamoDB table already exists: {table_name}")
    except Exception as e:
        print(f"❌ Error creating DynamoDB table: {e}")
        return False

    # 3. Create SNS topic for new tracks
    topic_name = 'new-tracks'
    try:
        topic_response = sns_client.create_topic(Name=topic_name)
        topic_arn = topic_response['TopicArn']
        print(f"✅ Created SNS topic: {topic_name}")
        print(f"   Topic ARN: {topic_arn}")
    except Exception as e:
        print(f"❌ Error creating SNS topic: {e}")
        return False

    # 4. Upload test chart data to S3
    chart_file_key = 'beatport/2024/08/09/top100-103000.json'

    # Read the test chart data
    try:
        with open('../events/test-chart-data.json', 'r') as f:
            chart_data = f.read()

        s3_client.put_object(
            Bucket=bucket_name,
            Key=chart_file_key,
            Body=chart_data,
            ContentType='application/json'
        )
        print(f"✅ Uploaded test chart data to S3: s3://{bucket_name}/{chart_file_key}")
    except Exception as e:
        print(f"❌ Error uploading test chart data: {e}")
        return False

    return True, topic_arn

def deploy_lambda_function():
    """Deploy the chart processor Lambda function to LocalStack"""

    print("🚀 Deploying Lambda function to LocalStack...")

    endpoint_url = 'http://localhost:4566'
    lambda_client = boto3.client('lambda', endpoint_url=endpoint_url, region_name='us-east-1')
    iam_client = boto3.client('iam', endpoint_url=endpoint_url, region_name='us-east-1')

    try:
        # Create IAM role for Lambda
        role_name = 'lambda-execution-role'
        assume_role_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {"Service": "lambda.amazonaws.com"},
                    "Action": "sts:AssumeRole"
                }
            ]
        }

        try:
            iam_client.create_role(
                RoleName=role_name,
                AssumeRolePolicyDocument=json.dumps(assume_role_policy)
            )
            print(f"✅ Created IAM role: {role_name}")
        except iam_client.exceptions.EntityAlreadyExistsException:
            print(f"✅ IAM role already exists: {role_name}")

        role_arn = f"arn:aws:iam::000000000000:role/{role_name}"

        # Check if Lambda package exists
        if not os.path.exists('chart-processor.zip'):
            print("📦 Creating Lambda package...")
            os.system('./package-lambda.sh > /dev/null 2>&1')

        # Read Lambda package
        with open('chart-processor.zip', 'rb') as f:
            zip_content = f.read()

        # Deploy Lambda function
        function_name = 'chart-processor'
        try:
            response = lambda_client.create_function(
                FunctionName=function_name,
                Runtime='python3.9',
                Role=role_arn,
                Handler='app.lambda_handler',
                Code={'ZipFile': zip_content},
                Environment={
                    'Variables': {
                        'TRACKS_TABLE': 'tracks',
                        'NEW_TRACKS_TOPIC_ARN': 'arn:aws:sns:us-east-1:000000000000:new-tracks'
                    }
                },
                Timeout=30
            )
            print(f"✅ Deployed Lambda function: {function_name}")
            print(f"   Function ARN: {response['FunctionArn']}")
            return True
        except lambda_client.exceptions.ResourceConflictException:
            # Function exists, update it
            lambda_client.update_function_code(
                FunctionName=function_name,
                ZipFile=zip_content
            )
            lambda_client.update_function_configuration(
                FunctionName=function_name,
                Environment={
                    'Variables': {
                        'TRACKS_TABLE': 'tracks',
                        'NEW_TRACKS_TOPIC_ARN': 'arn:aws:sns:us-east-1:000000000000:new-tracks'
                    }
                }
            )
            print(f"✅ Updated existing Lambda function: {function_name}")
            return True

    except Exception as e:
        print(f"❌ Error deploying Lambda function: {e}")
        return False

def test_chart_processor_locally():
    """Test the chart processor function locally (without Lambda)"""

    print("🧪 Testing chart processor function locally...")

    # Add the chart-processor directory to path
    sys.path.insert(0, os.path.abspath('.'))

    try:
        from app import lambda_handler

        # Set environment variables
        os.environ['TRACKS_TABLE'] = 'tracks'
        os.environ['NEW_TRACKS_TOPIC_ARN'] = 'arn:aws:sns:us-east-1:000000000000:new-tracks'
        os.environ['AWS_DEFAULT_REGION'] = 'us-east-1'

        # Configure boto3 to use LocalStack
        import boto3
        boto3.setup_default_session()

        # Load test event
        with open('../events/chart-processor-event.json', 'r') as f:
            event = json.load(f)

        # Execute function
        result = lambda_handler(event, None)

        print("📊 Function execution result:")
        print(json.dumps(result, indent=2))

        return result['statusCode'] == 200

    except Exception as e:
        print(f"❌ Error testing function locally: {e}")
        return False

def invoke_lambda_on_localstack():
    """Invoke the Lambda function on LocalStack"""

    print("🚀 Invoking Lambda function on LocalStack...")

    endpoint_url = 'http://localhost:4566'
    lambda_client = boto3.client('lambda', endpoint_url=endpoint_url, region_name='us-east-1')

    # Load test event
    with open('../events/chart-processor-event.json', 'r') as f:
        event = json.load(f)

    try:
        response = lambda_client.invoke(
            FunctionName='chart-processor',
            Payload=json.dumps(event),
            InvocationType='RequestResponse'
        )

        # Read response
        payload = response['Payload'].read().decode('utf-8')
        result = json.loads(payload)

        print("📊 Lambda execution result:")
        print(json.dumps(result, indent=2))

        return True

    except Exception as e:
        print(f"❌ Error invoking Lambda function: {e}")
        print("   Make sure the chart-processor Lambda function is deployed to LocalStack")
        return False

def main():
    """Main test execution"""

    print("🎵 Chart Processor LocalStack Test")
    print("=" * 40)

    # Setup resources
    setup_result = setup_localstack_resources()
    if not setup_result:
        print("❌ Failed to setup LocalStack resources")
        return

    success, topic_arn = setup_result
    if not success:
        return

    # Deploy Lambda function
    print("\n" + "=" * 40)
    deploy_success = deploy_lambda_function()
    if not deploy_success:
        print("❌ Failed to deploy Lambda function")
        print("   Will skip Lambda invocation test")

    # Test locally first
    print("\n" + "=" * 40)
    local_success = test_chart_processor_locally()

    if local_success:
        print("✅ Local test passed!")
    else:
        print("❌ Local test failed!")

    # Try Lambda invocation
    print("\n" + "=" * 40)
    if deploy_success:
        lambda_success = invoke_lambda_on_localstack()
        if lambda_success:
            print("✅ Lambda invocation successful!")
        else:
            print("❌ Lambda invocation failed!")
    else:
        print("⏭️  Skipping Lambda invocation (deployment failed)")

    print("\n🎉 Test completed!")
    print("\nNext steps:")
    print("1. Check LocalStack logs for detailed execution info")
    print("2. Verify DynamoDB tracks table for any existing tracks")
    print("3. Check SNS topic for published messages")
    print(f"4. S3 bucket 'charts-bucket' contains test data")
    if deploy_success:
        print("5. Lambda function 'chart-processor' is deployed and ready")

if __name__ == "__main__":
    main()
