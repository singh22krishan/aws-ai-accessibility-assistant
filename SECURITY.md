# Security and privacy notes

This portfolio version intentionally contains **no AWS credentials, bucket names, API keys, or personal identifiers**.

For a real deployment:

- Use an S3 bucket that is not public.
- Configure `S3_BUCKET` and `ALLOWED_ORIGIN` through deployment environment variables.
- Apply least-privilege IAM permissions; the example policy must be reviewed and adapted before use.
- Enable an S3 lifecycle policy for `auto-delete=true` audio objects. A one-day example is included because S3 lifecycle expiration is day-based, while the pre-signed URL itself expires after only a few minutes.
- Add API Gateway authentication, usage plans, throttling, or AWS WAF before exposing the endpoint broadly; otherwise anonymous requests can generate AWS service costs.
- Do not log generated OCR text or descriptions because uploaded images may contain personal or sensitive information.
- Keep CloudWatch retention appropriate for your environment.
