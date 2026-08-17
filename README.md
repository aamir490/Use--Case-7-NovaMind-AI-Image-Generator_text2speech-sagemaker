# NovaMind AI Image Generator

A serverless text-to-image web application on AWS. Users enter a text prompt in the browser; the backend invokes a Stable Diffusion model on Amazon SageMaker, stores the result in Amazon S3, and returns a pre-signed URL for display.

**Author:** [Aamir Imran](https://www.linkedin.com/in/aamir-imran/)

---

## Overview

NovaMind is a full-stack generative AI project that turns natural-language prompts into 512×512 JPEG images. The frontend is a single-page web app; the backend is event-driven and serverless. Long-running SageMaker inference is handled asynchronously so API Gateway does not time out.

---

## Architecture

```
Browser (index.html)
    │
    ├─ POST /generate  ──► API Gateway ──► Start_Processing_Function (Lambda)
    │                                              │
    │                                              └─ async invoke ──► Endpoint_Call_Function (Lambda)
    │                                                                        │
    │                                                                        ├─ invoke ──► SageMaker Endpoint (Stable Diffusion)
    │                                                                        └─ upload ──► S3 (generated_images/)
    │
    └─ GET /generate (poll every 5s) ──► API Gateway ──► Display_Image_Function (Lambda)
                                                              │
                                                              └─ pre-signed S3 URL ──► Browser
```

**Design decisions:**

- **Async processing** — `Start_Processing_Function` returns HTTP 200 immediately and invokes `Endpoint_Call_Function` with `InvocationType='Event'`, avoiding API Gateway's 29-second timeout during inference.
- **Polling** — The frontend polls `GET /generate` every 5 seconds (up to 120 seconds) until a new image appears in S3.
- **Exclude parameter** — `Display_Image_Function` accepts `?exclude=<previous-s3-key>` so polling returns only a newly generated image, not the previous one.
- **Pre-signed URLs** — Generated images are served via S3 pre-signed URLs (1-hour expiry), not public bucket access or CloudFront.

---

## AWS Services

| Service | Role |
|---------|------|
| **Amazon SageMaker AI** | Deploy Stable Diffusion via JumpStart; host inference endpoint |
| **AWS Lambda** | Three Python functions for orchestration, inference, and image retrieval |
| **Amazon API Gateway** | REST API with `POST /generate` and `GET /generate` |
| **Amazon S3** | Store generated images (`generated_images/`) and host the static website |
| **Amazon CloudFront** | Serve the frontend (`index.html`) only — not used for image delivery |
| **AWS IAM** | Execution roles and inline policies for SageMaker, Lambda, and S3 |

---

## AI Model

| Property | Value |
|----------|-------|
| Model | Stable Diffusion v2 (Stability AI) |
| Source | Amazon SageMaker JumpStart |
| Model ID | `model-txt2img-stabilityai-stable-diffusion-v2` |
| Version | `1.2.*` |
| Inference instance | `ml.g5.2xlarge` (primary notebook) / `ml.g5.xlarge` (alternate notebook) |
| Studio setup | JupyterLab on `ml.t3.large`, 25 GB storage |

The SageMaker deployment is defined in `text_2_image_with_generative_ai.ipynb` and `text_2_image_with_generative_ai_new_aamir-vey-final.ipynb`.

**Default inference payload** (from `index.html`):

```json
{
  "prompt": "<user input>",
  "negative_prompt": "blurry, low quality, person, human, face, text, watermark, ugly, distorted",
  "width": 512,
  "height": 512,
  "num_images_per_prompt": 1,
  "num_inference_steps": 50,
  "guidance_scale": 10
}
```

---

## Backend (Lambda)

| Function | File | Runtime | RAM | Timeout | Purpose |
|----------|------|---------|-----|---------|---------|
| `Start_Processing_Function` | `start_process_function.py` | Python 3.11 | 512 MB | 5 min | Accept POST, async-invoke processing Lambda |
| `Endpoint_Call_Function` | `endpoint_call_function.py` | Python 3.10 | 512 MB | 5 min | Call SageMaker, convert pixels to JPEG, upload to S3 |
| `Display_Image_Function` | `display_image.py` | Python 3.11 | 512 MB | 5 min | List S3, return pre-signed URL of latest (or new) image |

### Environment variables

| Lambda | Variable | Description |
|--------|----------|-------------|
| `Endpoint_Call_Function` | `ENDPOINT_NAME` | SageMaker endpoint name |
| `Endpoint_Call_Function` | `BUCKET_NAME` | S3 bucket for generated images |
| `Start_Processing_Function` | `PROCESSING_LAMBDA_NAME` | Name of `Endpoint_Call_Function` |
| `Start_Processing_Function` | `BUCKET_NAME` | S3 bucket name |
| `Display_Image_Function` | `BUCKET_NAME` | S3 bucket name |

### IAM permissions

| Lambda | Policies |
|--------|----------|
| `Endpoint_Call_Function` | `AmazonS3FullAccess`, `AmazonSageMakerFullAccess` |
| `Start_Processing_Function` | `AmazonS3FullAccess`, `AWSLambda_FullAccess` |
| `Display_Image_Function` | `AmazonS3FullAccess` |

`Endpoint_Call_Function` requires a **Pillow Lambda Layer** (`pillowlayer.zip`, Python 3.10 x86_64) for JPEG conversion. A vendored Pillow 10.1.0 copy is included under `python/` for layer packaging.

---

## Frontend

**File:** `index.html`

| Aspect | Details |
|--------|---------|
| Stack | HTML, CSS, JavaScript (no framework) |
| Hosting | S3 + CloudFront |
| Features | Prompt input (max 300 chars), loading spinner, progress bar, countdown timer, retry logic, configurable API URL |
| Config | Settings panel — API Gateway URL, request timeout (30–300 s), max retries (1–10); persisted in `localStorage` |
| Keyboard | `Ctrl/Cmd + Enter` to generate |

**Request flow:**

1. `POST` prompt to API Gateway `/generate`
2. Record the current latest S3 key via `GET /generate`
3. Poll `GET /generate?exclude=<previous-key>` every 5 seconds
4. On HTTP 200, load the pre-signed URL into an `<img>` tag
5. On HTTP 202, continue polling (image not ready)

---

## API

**Definition:** `text-image-generative-ai-api-prod-swagger-apigateway.json`

| Method | Path | Lambda integration |
|--------|------|--------------------|
| `POST` | `/generate` | `Start_Processing_Function` |
| `GET` | `/generate` | `Display_Image_Function` |
| `OPTIONS` | `/generate` | CORS mock |

CORS is enabled (`Access-Control-Allow-Origin: *`) on all Lambda responses.

---

## Repository Structure

```
├── index.html                                      # Frontend web application
├── start_process_function.py                       # Async trigger Lambda
├── endpoint_call_function.py                       # SageMaker + S3 upload Lambda
├── display_image.py                                # S3 image retrieval Lambda
├── text_2_image_with_generative_ai.ipynb           # SageMaker JumpStart deployment notebook
├── text_2_image_with_generative_ai_new_aamir-vey-final.ipynb
├── text-image-generative-ai-api-prod-swagger-apigateway.json
├── Bucket_Policy_S3.json                           # S3 bucket policy (direct access)
├── Bucket_Policy_S3_cloudfront.json                # S3 bucket policy (CloudFront OAC)
├── python/                                         # Vendored Pillow 10.1.0 (Lambda layer source)
├── steps_to_do.md                                  # Detailed deployment guide
├── github.md                                       # Project notes and git commands
└── ReadersAreTheLeaders.txt                        # Original setup checklist
```

---

## Setup and Deployment

Full step-by-step instructions are in [`steps_to_do.md`](steps_to_do.md). Summary:

### 1. SageMaker — Deploy the model

1. Create a SageMaker Studio user and JupyterLab space (`ml.t3.large`, 25 GB).
2. Grant the SageMaker execution role `S3FullAccess`.
3. Run `text_2_image_with_generative_ai.ipynb` (Steps 1–4 minimum).
4. Wait for the endpoint to reach **InService** (~10–15 minutes).

### 2. S3 — Create storage

- **Images bucket:** e.g. `cloudage-text-to-image-webappp-new` in `us-east-1`, with folder `generated_images/`. Block all public access.
- **Website bucket:** separate bucket for `index.html` and logo assets.

### 3. Lambda — Deploy three functions

Deploy the three `.py` files with the environment variables and permissions listed above. Attach the Pillow layer to `Endpoint_Call_Function`.

### 4. API Gateway — Wire the API

1. Import `text-image-generative-ai-api-prod-swagger-apigateway.json`.
2. Link `POST /generate` → `Start_Processing_Function`.
3. Link `GET /generate` → `Display_Image_Function`.
4. Deploy to a stage (e.g. `prodd`).

### 5. Frontend — Configure and host

1. Set the API Gateway URL in `index.html` (or via the settings panel).
2. Upload `index.html` and logo files to the website S3 bucket.
3. Create a CloudFront distribution with `index.html` as the default root object.
4. Apply the CloudFront OAC bucket policy from `Bucket_Policy_S3_cloudfront.json`.

---

## Operational Notes

- The SageMaker endpoint must be **InService** before generating images.
- A **GPU instance** (`ml.g4dn.xlarge` or larger) is required to avoid inference timeouts.
- Pre-signed URLs expire after **1 hour**.
- Generated images accumulate in `generated_images/` — periodic cleanup reduces S3 costs.
- CloudFront serves only the website; image delivery uses S3 pre-signed URLs directly.

---

## Interview Talking Points

1. **Why async Lambda invocation?** SageMaker inference can take 30–90+ seconds. API Gateway times out at 29 seconds. The fire-and-forget pattern decouples the HTTP response from inference.
2. **Why polling instead of WebSockets?** Simpler architecture with no persistent connections. The `exclude` query parameter prevents returning stale images.
3. **Why pre-signed URLs over public S3?** Keeps the bucket private while allowing time-limited, direct browser access without a CloudFront distribution for images.
4. **Why Pillow in a Lambda layer?** SageMaker returns raw pixel arrays; Pillow converts them to JPEG before S3 upload. Layers keep the deployment package small.
5. **Cost awareness** — SageMaker GPU endpoints, S3 storage, Lambda invocations, API Gateway requests, and CloudFront data transfer all incur charges. The endpoint should be deleted when not in use.

---

## License

This project was built as an educational AWS generative AI use case. Refer to AWS and Stability AI terms for model usage and deployment licensing.
