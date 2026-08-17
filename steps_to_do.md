# AWS Text-to-Image Project — Complete Setup Guide

> All Praise Be To Almighty GOD Alone.
> This guide includes all original steps plus corrections applied during debugging to make the project fully working.

---

## Project Architecture

```
User (Browser)
    |
    | POST /generate (prompt)
    v
API Gateway
    |
    | triggers
    v
Start_Processing_Function (Lambda)
    |
    | async invoke
    v
Endpoint_Call_Function (Lambda)
    |
    | invokes
    v
SageMaker Endpoint (Stable Diffusion Model)
    |
    | returns image pixel data
    v
Endpoint_Call_Function
    |
    | uploads JPEG to S3
    | generates pre-signed URL
    v
S3 Bucket (generated_images/)
    |
    | GET /generate (poll)
    v
Display_Image_Function (Lambda)
    |
    | lists S3, gets latest image
    | generates pre-signed URL
    v
API Gateway
    |
    | returns image URL
    v
Browser displays image
```

---

## PART 1 — SageMaker Setup

### Step 1 — Log into AWS Console and go to Amazon SageMaker AI

### Step 1a — Create a SageMaker Studio User
- Go to SageMaker AI → Studio
- Click **Create User** with default settings
- Wait for the user to be created

### Step 1b — Launch Studio and Create a JupyterLab Space
- Click **Launch Studio**
- Create a new **JupyterLab Space** with these settings:
  - Instance: `ml.t3.large`
  - Storage: `25 GB`
- Wait for the space to start

### Step 1c — Import the Jupyter Notebook
- Open JupyterLab
- Upload the file `jupyter_notebook.ipynb` from your desktop
- Open it

### Step 1d — Add S3 Permissions to SageMaker Execution Role
The notebook needs S3 access to store the model. Do this before running any code:

1. Go to **AWS IAM Console**
2. Navigate to **Roles**
3. Search for and select your SageMaker execution role:
   `AmazonSageMaker-ExecutionRole-XXXXXXXXXXXXXXX`
4. Click **Add permissions** → **Create inline policy**
5. Add **S3FullAccess** policy
6. Click **Save**

### Step 1e — Run the Notebook
- Run all code cells from **Step 1 through Step 4** at minimum
- Then continue running all remaining sections
- This will download the Stable Diffusion model and deploy it as a SageMaker endpoint
- **Note:** Deployment takes 10–15 minutes. Wait until the endpoint status shows **InService**
- After completion, note down your endpoint name from:
  `SageMaker → Deployments → Endpoints`
  Example: `cloudage-endpoint-text-to-image-model-t-2026-08-16-18-17-47-946`

---

## PART 2 — S3 Bucket Setup

### Step 2-S3 — Create an S3 Bucket for Generated Images
1. Go to **AWS S3 → Create Bucket**
2. Bucket name: `cloudage-text-to-image-webappp-new` (note the double 'p')
3. Region: `us-east-1`
4. Keep **Block all public access** turned ON (images are served via pre-signed URLs, not public)
5. Click **Create bucket**
6. Inside the bucket, create a folder named: `generated_images/`

---

## PART 3 — Lambda Functions Setup

### Step 3 — Go to AWS Lambda and Create Three Functions

---

### Function 1 — Endpoint_Call_Function

**Purpose:** Receives the prompt, calls SageMaker, converts the result to a JPEG image, uploads it to S3, and returns a pre-signed URL.

**Configuration:**
| Setting | Value |
|---------|-------|
| Runtime | Python 3.10 |
| RAM | 512 MB |
| Timeout | 5 minutes |

**Environment Variables:**
| Key | Value |
|-----|-------|
| `ENDPOINT_NAME` | your SageMaker endpoint name (e.g. `cloudage-endpoint-text-to-image-model-t-2026-08-16-18-17-47-946`) |
| `BUCKET_NAME` | `cloudage-text-to-image-webappp-new` |

> ⚠️ Do NOT add a `CLOUDFRONT_DOMAIN` variable. The updated code uses pre-signed S3 URLs instead of CloudFront.

**Permissions:**
- `AmazonS3FullAccess`
- `AmazonSageMakerFullAccess`

**Add Pillow Layer:**
1. Go to **Lambda → Layers → Create Layer**
2. Name: `PillowLayer`
3. Upload `pillowlayer.zip`
4. Runtime: `Python 3.10 x86_64`
5. Click **Create**
6. Go to **Lambda → Functions → Endpoint_Call_Function**
7. Scroll down to **Layers → Add a layer**
8. Choose **Custom layers** → select `PillowLayer` → **Add**

**Code — paste this into the Lambda code editor:**
```python
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

logger = logging.getLogger()
logger.setLevel(logging.INFO)

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
    s3_client.upload_fileobj(buffer, bucket_name, s3_key, ExtraArgs={'ContentType': 'image/jpeg'})
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
    encoded_payload = cleaned_body.encode("utf-8")

    response = sagemaker_client.invoke_endpoint(
        EndpointName=os.environ["ENDPOINT_NAME"],
        ContentType="application/json",
        Body=encoded_payload
    )

    result = json.loads(response["Body"].read().decode())

    if "generated_images" in result:
        s3_key = create_and_upload_image(result["generated_images"][0])
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
```

Click **Deploy** after pasting.

---

### Function 2 — Start_Processing_Function

**Purpose:** Receives the POST request from API Gateway and immediately returns a 200 response, then asynchronously triggers `Endpoint_Call_Function` in the background (so API Gateway does not time out).

**Configuration:**
| Setting | Value |
|---------|-------|
| Runtime | Python 3.11 |
| RAM | 512 MB |
| Timeout | 5 minutes |

**Environment Variables:**
| Key | Value |
|-----|-------|
| `PROCESSING_LAMBDA_NAME` | `Endpoint_Call_Function` |
| `BUCKET_NAME` | `cloudage-text-to-image-webappp-new` |

**Permissions:**
- `AmazonS3FullAccess`
- `AWSLambda_FullAccess`

**Code — paste this into the Lambda code editor:**
```python
# Environment Variables:
# PROCESSING_LAMBDA_NAME: Endpoint_Call_Function
# BUCKET_NAME: cloudage-text-to-image-webappp-new

import json
import boto3
import os
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

lambda_client = boto3.client('lambda')

def lambda_handler(event, context):
    logger.info('Event: %s', json.dumps(event))

    processing_lambda_name = os.environ["PROCESSING_LAMBDA_NAME"]
    lambda_client.invoke(
        FunctionName=processing_lambda_name,
        InvocationType='Event',  # Asynchronous — fire and forget
        Payload=json.dumps(event)
    )

    return {
        'statusCode': 200,
        'headers': {
            'Access-Control-Allow-Headers': 'Content-Type',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'OPTIONS,POST'
        },
        'body': json.dumps({'message': 'Request received, processing started'})
    }
```

Click **Deploy** after pasting.

---

### Function 3 — Display_Image_Function

**Purpose:** Called by the frontend (GET request) to retrieve the URL of the most recently generated image from S3. Returns a pre-signed URL valid for 1 hour.

**Configuration:**
| Setting | Value |
|---------|-------|
| Runtime | Python 3.11 |
| RAM | 512 MB |
| Timeout | 5 minutes |

**Environment Variables:**
| Key | Value |
|-----|-------|
| `BUCKET_NAME` | `cloudage-text-to-image-webappp-new` |

**Permissions:**
- `AmazonS3FullAccess`

> ⚠️ Remove `CloudFrontFullAccess` — it is no longer needed. The updated code does not use CloudFront at all.

**Code — paste this into the Lambda code editor:**
```python
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

    response = s3_client.list_objects_v2(Bucket=bucket_name, Prefix=prefix)

    if 'Contents' in response:
        # Get the most recently uploaded image
        files = sorted(response['Contents'], key=itemgetter('LastModified'), reverse=True)
        latest_file = files[0]['Key']
        logger.info('Latest file in S3: %s', latest_file)

        # Generate a pre-signed URL valid for 1 hour — no CloudFront needed
        image_url = s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': bucket_name, 'Key': latest_file},
            ExpiresIn=3600
        )
        logger.info('Pre-signed URL: %s', image_url)

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
```

Click **Deploy** after pasting.

---

## PART 4 — API Gateway Setup

### Step 4 — Go to AWS API Gateway → REST API

### Step 4a — Import the API
1. Click **Create API** → **REST API** → **Import**
2. Upload the file: `generative-ai-api-prod-swagger-apigateway.json`
3. Click **Import**

### Step 4b — Review Resources and Stages
- You should see two resources: `POST /generate` and `GET /generate`
- Review that they exist

### Step 4c — Link Lambda Functions to API Resources

**POST resource (triggers image generation):**
1. Click on **POST** under `/generate`
2. Click **Integration Request**
3. Click the edit (pencil) icon next to Lambda Function
4. Replace with: `Start_Processing_Function`
5. Click the checkmark to save
6. When prompted to add permissions, click **OK**

**GET resource (retrieves the generated image URL):**
1. Click on **GET** under `/generate`
2. Click **Integration Request**
3. Click the edit (pencil) icon next to Lambda Function
4. Replace with: `Display_Image_Function`
5. Click the checkmark to save
6. When prompted to add permissions, click **OK**

### Step 4d — Deploy the API
1. Click **Actions** → **Deploy API**
2. Stage: Create a new stage (e.g. `prodd` or your organisation's name)
3. Click **Deploy**
4. Copy the **Invoke URL** — it looks like:
   `https://xxxxxxxxxx.execute-api.us-east-1.amazonaws.com/prodd`
5. Your full POST URL will be:
   `https://xxxxxxxxxx.execute-api.us-east-1.amazonaws.com/prodd/generate`

---

## PART 5 — Frontend Setup

### Step 5 — Edit index.html

Open `index.html` and find this line inside the `Config` class constructor:

```javascript
this.apiUrl = "https://64t44fufi4.execute-api.us-east-1.amazonaws.com/prodd/generate";
```

Replace the URL with your own API Gateway POST URL that you copied in Step 4d.

### Step 5a — Upload Frontend Files to S3

1. Go to **AWS S3**
2. Create a new bucket (or use existing) for the website files
3. Upload these two files:
   - `index.html`
   - `cloudage_logo.jpeg`
4. Keep this bucket separate from the images bucket (`cloudage-text-to-image-webappp-new`)

---

## PART 6 — CloudFront Setup (for the Website only)

> **Important:** CloudFront is used ONLY to serve the website (`index.html`).  
> Generated images are served directly from S3 using pre-signed URLs — CloudFront is NOT involved for images.

### Step 6 — Create a CloudFront Distribution
1. Go to **AWS CloudFront → Create Distribution**
2. Origin domain: select your **website S3 bucket** (the one with `index.html`)
3. Origin access: **Origin access control settings (recommended)**
4. Create a new OAC if prompted
5. Click **Create distribution**

### Step 6a — Set Default Root Object
- CloudFront Distribution → **General** → **Edit**
- Default root object: `index.html`
- Click **Save changes**

### Step 6b — Update S3 Bucket Policy for CloudFront
1. CloudFront Distribution → **Origins** → select your origin → **Edit**
2. Click **Copy policy**
3. Go to your **website S3 bucket** → **Permissions** → **Bucket policy**
4. Paste the copied policy
5. Click **Save**

### Step 6c — Wait for Deployment
- Status changes from **Deploying** to **Enabled** (takes ~10 minutes)

### Step 6d — Create Invalidation
1. CloudFront Distribution → **Invalidations** → **Create invalidation**
2. Object path: `/*`
3. Click **Create invalidation**

### Step 6e — Access the Web App
- Go to the **Distribution domain name** shown in CloudFront
- Example: `https://abc123xyz.cloudfront.net`
- The web app will load and you can start generating images

- Prompt :- 
1. A cute orange cat sitting on a sofa and looking at the camera.

1. Cat
A cute orange cat sitting on a sofa.

2. Dog
A golden retriever playing in a park.

3. Mountain
A beautiful mountain with snow under a blue sky.

4. Car
A red sports car parked on a city street.

5. Beach
A peaceful beach with palm trees at sunset.



---

## PART 7 — Troubleshooting & Fixes Applied

### Problem: `ERR_NAME_NOT_RESOLVED` on image URL
**Cause:** The original `Display_Image_Function` and `Endpoint_Call_Function` were building image URLs using a CloudFront domain that did not exist or was deleted.

**Fix Applied:**
- Both Lambda functions now generate **pre-signed S3 URLs** instead of CloudFront URLs
- Pre-signed URLs are direct, temporary links to S3 objects valid for 1 hour
- No CloudFront distribution is needed for image delivery
- The `CLOUDFRONT_DOMAIN` environment variable is no longer used and can be deleted

### Problem: Lambda code not taking effect after editing local files
**Cause:** Editing files on your desktop does not automatically update Lambda.  
**Fix:** You must always copy the code and paste it directly into the Lambda console editor, then click **Deploy**.

### Problem: `sanitizeInput()` corrupting the prompt
**Cause:** The original `callApi()` function passed the prompt through `sanitizeInput()` which converts characters like `"` into HTML entities (`&quot;`), breaking the JSON payload sent to SageMaker.  
**Fix Applied:** Removed `sanitizeInput()` from the prompt — the raw text value is now used directly.

---

## Summary of All Files and Their Purpose

| File | Used In | Purpose |
|------|---------|---------|
| `endpoint_call_function.py` | Lambda: `Endpoint_Call_Function` | Calls SageMaker, converts image, uploads to S3, returns pre-signed URL |
| `start_process_function.py` | Lambda: `Start_Processing_Function` | Async trigger — immediately returns 200, fires Endpoint_Call_Function |
| `display_image.py` | Lambda: `Display_Image_Function` | Lists S3 bucket, finds latest image, returns pre-signed URL |
| `index.html` | S3 / CloudFront (website) | Frontend web app — takes prompt, calls API, displays image |
| `pillowlayer.zip` | Lambda Layer | Pillow image library for Python 3.10 |
| `cloudage_logo.jpeg` | S3 / CloudFront (website) | Logo shown in the web app |
| `Bucket_Policy_S3.json` | S3 Bucket | Bucket policy for direct S3 access |
| `Bucket_Policy_S3_cloudfront.json` | S3 Bucket | Bucket policy when using CloudFront for website |

---

## Environment Variables Quick Reference

| Lambda Function | Variable | Value |
|----------------|----------|-------|
| `Endpoint_Call_Function` | `ENDPOINT_NAME` | Your SageMaker endpoint name |
| `Endpoint_Call_Function` | `BUCKET_NAME` | `cloudage-text-to-image-webappp-new` |
| `Start_Processing_Function` | `PROCESSING_LAMBDA_NAME` | `Endpoint_Call_Function` |
| `Start_Processing_Function` | `BUCKET_NAME` | `cloudage-text-to-image-webappp-new` |
| `Display_Image_Function` | `BUCKET_NAME` | `cloudage-text-to-image-webappp-new` |

---

*Ask Bigger Questions. This is a Foundation Model named Stable Diffusion trained on AWS dataset. You can deploy other models from SageMaker AI — however, your organisation will need to bear the cost.*

*Great Work! Project Completed. All Praise Be To Almighty GOD Alone.*
