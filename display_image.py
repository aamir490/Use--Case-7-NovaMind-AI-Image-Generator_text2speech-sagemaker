# Environment Variables needed in Lambda:
# BUCKET_NAME: "cloudage-text-to-image-webappp-new"

import json
import boto3
import os
import logging
from operator import itemgetter

logger = logging.getLogger()
logger.setLevel(logging.INFO)

s3_client = boto3.client('s3')


def lambda_handler(event, context):
    logger.info('Event: %s', json.dumps(event))

    bucket_name = os.environ['BUCKET_NAME']
    prefix = 'generated_images/'

    # Optional: frontend passes the last known filename to exclude it
    # so we only return a NEW image different from the previous one
    exclude_key = None
    try:
        params = event.get('queryStringParameters') or {}
        if params.get('exclude'):
            exclude_key = params['exclude']
            logger.info('Excluding previous image: %s', exclude_key)
    except Exception as e:
        logger.warning('Could not parse exclude param: %s', e)

    response = s3_client.list_objects_v2(Bucket=bucket_name, Prefix=prefix)

    if 'Contents' in response:
        files = sorted(response['Contents'], key=itemgetter('LastModified'), reverse=True)

        if exclude_key:
            # Find a file that is not the excluded (previous) one
            new_files = [f for f in files if f['Key'] != exclude_key]
            if new_files:
                latest_file = new_files[0]['Key']
                logger.info('New image found: %s', latest_file)
            else:
                # No new image yet — tell frontend to keep polling
                logger.info('No new image yet, only previous image exists')
                return {
                    'statusCode': 202,
                    'headers': {
                        'Access-Control-Allow-Headers': 'Content-Type',
                        'Access-Control-Allow-Origin': '*',
                        'Access-Control-Allow-Methods': 'OPTIONS,GET'
                    },
                    'body': json.dumps({'status': 'pending'})
                }
        else:
            latest_file = files[0]['Key']
            logger.info('Returning latest image: %s', latest_file)

        image_url = s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': bucket_name, 'Key': latest_file},
            ExpiresIn=3600
        )

        return {
            'statusCode': 200,
            'headers': {
                'Access-Control-Allow-Headers': 'Content-Type',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'OPTIONS,GET'
            },
            'body': image_url
        }

    return {
        'statusCode': 404,
        'headers': {
            'Access-Control-Allow-Headers': 'Content-Type',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'OPTIONS,GET'
        },
        'body': json.dumps({'error': 'No images found in S3'})
    }
