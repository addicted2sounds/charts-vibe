import json
import os

import boto3
from boto3.dynamodb.conditions import Attr


def lambda_handler(event, context):
    table_name = os.environ.get('PLAYLISTS_TABLE', 'charts-vibe-playlists')
    function_name = os.environ.get('PLAYLIST_FUNCTION_NAME')
    if not function_name:
        return {
            'statusCode': 500,
            'body': json.dumps({'error': 'PLAYLIST_FUNCTION_NAME is not configured'})
        }

    resume_statuses = [
        status.strip()
        for status in os.environ.get('RESUME_STATUSES', 'rate_limited').split(',')
        if status.strip()
    ]
    batch_limit = int(os.environ.get('RESUME_BATCH_LIMIT', '5'))

    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table(table_name)
    lambda_client = boto3.client('lambda')

    filter_expression = None
    for status in resume_statuses:
        condition = Attr('status').eq(status)
        filter_expression = condition if filter_expression is None else (filter_expression | condition)

    projection_expression = 'playlist_id, s3_bucket, s3_key, resume_from, playlist_name, description, job_id, #status'
    expression_attribute_names = {'#status': 'status'}

    invoked = 0
    scanned = 0
    last_evaluated_key = None

    while True:
        scan_kwargs = {
            'FilterExpression': filter_expression,
            'ProjectionExpression': projection_expression,
            'ExpressionAttributeNames': expression_attribute_names
        }
        if last_evaluated_key:
            scan_kwargs['ExclusiveStartKey'] = last_evaluated_key

        response = table.scan(**scan_kwargs)
        items = response.get('Items', [])
        scanned += len(items)

        for item in items:
            if invoked >= batch_limit:
                break

            s3_bucket = item.get('s3_bucket')
            s3_key = item.get('s3_key')
            playlist_id = item.get('playlist_id')

            if not s3_bucket or not s3_key or not playlist_id:
                print(f"Skipping playlist without S3 context: {playlist_id}")
                continue

            resume_from = item.get('resume_from', 0)
            try:
                resume_from = int(resume_from)
            except (TypeError, ValueError):
                resume_from = 0

            payload = {
                's3_bucket': s3_bucket,
                's3_key': s3_key,
                'playlist_id': playlist_id,
                'resume_from': resume_from,
                'playlist_name': item.get('playlist_name'),
                'description': item.get('description'),
                'job_id': item.get('job_id'),
                'resume': True
            }

            try:
                lambda_client.invoke(
                    FunctionName=function_name,
                    InvocationType='Event',
                    Payload=json.dumps(payload).encode('utf-8')
                )
                invoked += 1
                print(f"Invoked playlist resume for {playlist_id} from index {resume_from}")
            except Exception as e:
                print(f"Failed to invoke playlist resume for {playlist_id}: {str(e)}")

        last_evaluated_key = response.get('LastEvaluatedKey')
        if not last_evaluated_key or invoked >= batch_limit:
            break

    return {
        'statusCode': 200,
        'body': json.dumps({
            'invoked': invoked,
            'scanned': scanned,
            'batch_limit': batch_limit,
            'statuses': resume_statuses
        })
    }
