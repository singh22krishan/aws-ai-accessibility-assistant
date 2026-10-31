# AWS AI Accessibility Assistant

A serverless accessibility-focused application that turns an uploaded image into a generated description and spoken MP3 using managed AWS AI services.

## Architecture

```text
Browser
  ↓ multipart upload
AWS Chalice / API Gateway
  ↓
Private Amazon S3 temporary object
  ├─ Amazon Rekognition → image labels + OCR text
  ├─ Amazon Translate   → optional language translation
  └─ Amazon Polly       → MP3 speech
                         ↓
                 Private S3 audio object
                         ↓
                 Short-lived pre-signed URL
```

## Features

- JPEG/PNG upload validation and configurable 5 MB default limit
- Amazon Rekognition label detection and OCR
- Optional translation to Spanish, French, German, or Hindi
- Amazon Polly multilingual speech generation
- Server-side encryption requested for temporary S3 objects
- Five-minute default pre-signed audio URL
- Temporary source-image cleanup in a `finally` block
- CORS origin configured through the environment rather than opened to every origin
- Privacy-conscious logging that does not write OCR text/descriptions to logs
- S3 lifecycle and IAM policy examples for deployment hardening

## Security design

The original academic version used a hard-coded S3 bucket, broad CORS, success-path-only image cleanup, and logged generated descriptions. This portfolio version removes those deployment-specific values and reduces unnecessary exposure.

No AWS access keys or secrets are included. AWS SDK credentials should be supplied through the standard AWS credential chain / execution role.

Before exposing the service to the public Internet, add API Gateway authentication/throttling or AWS WAF so anonymous users cannot create uncontrolled Rekognition, Translate, Polly, and S3 costs. See `SECURITY.md`.

## Local development

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Configure the deployment environment variables from `.env.example`, authenticate with an AWS development profile or role, then run:

```bash
chalice local
```

Serve `frontend/` with a local static web server and update `frontend/config.js` or replace it at deployment time with your API Gateway URL.

## Academic context

This repository is a cleaned portfolio version of an academic cloud/AI project. Deployment-specific identifiers and local-machine artifacts from the source ZIP have been removed.

## Skills demonstrated

AWS · Serverless Architecture · Python · Chalice · API Gateway · Amazon S3 · Rekognition · Translate · Polly · REST APIs · Accessibility · Secure Configuration
