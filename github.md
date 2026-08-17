# NovaMind AI Image Generator — Project Notes

> Built by [Aamir Imran](https://www.linkedin.com/in/aamir-imran/)

---

## Project Overview

A serverless text-to-image web application built on AWS using Stable Diffusion via Amazon SageMaker. Users type a text prompt and the app generates an AI image in real time.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | HTML, CSS, JavaScript (hosted on S3 + CloudFront) |
| API | AWS API Gateway (REST API) |
| Backend | AWS Lambda (Python 3.10 / 3.11) |
| AI Model | Stable Diffusion v1.4 via Amazon SageMaker |
| Storage | Amazon S3 |
| Image Delivery | S3 Pre-signed URLs |

---

## Repository Files

| File | Purpose |
|------|---------|
| `index.html` | Frontend web app — takes prompt, calls API, displays generated image |
| `endpoint_call_function.py` | Lambda — calls SageMaker endpoint, uploads image to S3, returns pre-signed URL |
| `start_process_function.py` | Lambda — async trigger, immediately returns 200 and fires Endpoint_Call_Function |
| `display_image.py` | Lambda — finds latest new image in S3, returns pre-signed URL |
| `pillowlayer.zip` | Lambda Layer — Pillow image library for Python 3.10 |
| `steps_to_do.md` | Full detailed deployment guide with all fixes documented |
| `Bucket_Policy_S3.json` | S3 bucket policy for direct access |
| `Bucket_Policy_S3_cloudfront.json` | S3 bucket policy for CloudFront access |

---

## Architecture Flow

```
User types prompt
        |
        v
API Gateway POST /generate
        |
        v
Start_Processing_Function (Lambda)
  - Returns 200 immediately
  - Async invokes Endpoint_Call_Function
        |
        v
Endpoint_Call_Function (Lambda)
  - Calls SageMaker Stable Diffusion endpoint
  - Converts pixel data to JPEG
  - Uploads to S3 bucket (generated_images/)
        |
        v
Frontend polls GET /generate every 5 seconds
        |
        v
Display_Image_Function (Lambda)
  - Lists S3 bucket
  - Returns pre-signed URL of newest image
        |
        v
Browser displays generated image
```

---

## Key AWS Resources

| Resource | Name |
|----------|------|
| S3 Bucket (images) | `cloudage-text-to-image-webappp-new` |
| SageMaker Endpoint | `cloudage-endpoint-text-to-image-model-t-2026-08-16-18-17-47-946` |
| API Gateway Stage | `prodd` |
| Lambda Runtime (Endpoint) | Python 3.10 |
| Lambda Runtime (Others) | Python 3.11 |

---

## Environment Variables

| Lambda | Variable | Value |
|--------|----------|-------|
| `Endpoint_Call_Function` | `ENDPOINT_NAME` | SageMaker endpoint name |
| `Endpoint_Call_Function` | `BUCKET_NAME` | `cloudage-text-to-image-webappp-new` |
| `Start_Processing_Function` | `PROCESSING_LAMBDA_NAME` | `Endpoint_Call_Function` |
| `Start_Processing_Function` | `BUCKET_NAME` | `cloudage-text-to-image-webappp-new` |
| `Display_Image_Function` | `BUCKET_NAME` | `cloudage-text-to-image-webappp-new` |

---

## Key Fixes Applied During Development

1. **ERR_NAME_NOT_RESOLVED** — CloudFront domain was invalid. Fixed by replacing CloudFront URLs with S3 pre-signed URLs in both `Endpoint_Call_Function` and `Display_Image_Function`.

2. **Wrong image returned** — `Display_Image_Function` always returned the latest S3 file regardless of when it was uploaded. Fixed by passing `?exclude=<previous-key>` so Lambda skips the old image and waits for a new one.

3. **SageMaker invocation timeout** — `num_inference_steps: 75` caused the model container to exceed its response timeout. Fixed by reducing back to `50` steps.

4. **CORS error on image load** — `fetch()` probe before `img.src` failed due to CORS on S3 pre-signed URLs. Fixed by removing the probe and setting `img.src` directly (img tags are not subject to CORS).

5. **Prompt sanitization breaking API** — `sanitizeInput()` was converting prompt characters to HTML entities before sending to SageMaker. Fixed by removing sanitization from the prompt value.

---

## Important Notes

- SageMaker endpoint must be **InService** before generating images
- Stable Diffusion requires a **GPU instance** (`ml.g4dn.xlarge` recommended) to avoid inference timeouts
- S3 pre-signed URLs expire after **1 hour** — download images before they expire
- Generated images accumulate in S3 — clean up `generated_images/` folder periodically to reduce storage costs
- CloudFront is used only for serving the website (`index.html`) — NOT for image delivery

---

*All Praise Be To Almighty GOD Alone.*
