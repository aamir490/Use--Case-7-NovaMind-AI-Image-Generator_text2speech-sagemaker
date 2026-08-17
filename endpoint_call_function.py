# Environment Variables needed in Lambda:
# ENDPOINT_NAME: your SageMaker endpoint name
# BUCKET_NAME:   your S3 bucket name (e.g. cloudage-text-to-image-webappp-new)

import json
import boto3
import os
import logging
from PIL import Image
import io
import uuid

# Set up logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# AWS clients
sagemaker_client = boto3.client("sagemaker-runtime")
s3_client = boto3.client('s3')

bucket_name = os.environ['BUCKET_NAME']
s3_folder = 'generated_images/'


def create_and_upload_image(image_data):
    """Convert raw pixel data to JPEG and upload to S3. Returns the S3 key."""
    image = Image.new("RGB", (len(image_data[0]), len(image_data)))
    pixels = image.load()

    for i in range(image.width):
        for j in range(image.height):
            pixels[i, j] = tuple(image_data[j][i])

    buffer = io.BytesIO()
    image.save(buffer, format="JPEG")
    buffer.seek(0)

    file_name = f'generated-image-{uuid.uuid4()}.jpg'
    s3_key = f'{s3_folder}{file_name}'

    s3_client.upload_fileobj(
        buffer,
        bucket_name,
        s3_key,
        ExtraArgs={'ContentType': 'image/jpeg'}
    )
    logger.info('Uploaded image to s3://%s/%s', bucket_name, s3_key)
    return s3_key


def get_presigned_url(s3_key, expiry_seconds=3600):
    """Generate a pre-signed URL so the browser can load the image directly from S3."""
    url = s3_client.generate_presigned_url(
        'get_object',
        Params={'Bucket': bucket_name, 'Key': s3_key},
        ExpiresIn=expiry_seconds
    )
    logger.info('Pre-signed URL: %s', url)
    return url


def lambda_handler(event, context):
    logger.info('Event: %s', json.dumps(event))

    body_content = json.loads(event['body'])
    cleaned_body = json.dumps(body_content, separators=(',', ':'))
    logger.info('Cleaned body: %s', cleaned_body)

    encoded_payload = cleaned_body.encode("utf-8")

    response = sagemaker_client.invoke_endpoint(
        EndpointName=os.environ["ENDPOINT_NAME"],
        ContentType="application/json",
        Body=encoded_payload
    )

    result = json.loads(response["Body"].read().decode())

    if "generated_images" in result:
        s3_key = create_and_upload_image(result["generated_images"][0])

        # Use a pre-signed S3 URL — no CloudFront needed, works immediately
        image_url = get_presigned_url(s3_key, expiry_seconds=3600)

        return {
            'statusCode': 200,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': 'Content-Type',
                'Access-Control-Allow-Methods': 'OPTIONS,POST'
            },
            'body': json.dumps({'cloudFrontUrl': image_url})
        }

    logger.error('Unexpected response format: %s', result)
    return {
        'statusCode': 400,
        'headers': {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': 'Content-Type',
            'Access-Control-Allow-Methods': 'OPTIONS,POST'
        },
        'body': json.dumps({'error': 'No generated_images in model response'})
    }
