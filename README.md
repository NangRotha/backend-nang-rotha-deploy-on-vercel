# Nang Rotha Portfolio API

FastAPI backend for the portfolio. Project images, profile images, and CV files
are stored on UploadThing; their public URLs are stored in Supabase.

## Environment

Copy `.env.example` to `.env` and configure:

- `SUPABASE_URL`
- `SUPABASE_KEY`
- `UPLOADTHING_TOKEN` (the **SDK v7+ token**, not the legacy secret)
- `DEEPSEEK_API_KEY` (server-side only, used by chat and translation)
- `DEEPSEEK_MODEL` (optional; defaults to `deepseek-flash`)

Never commit `.env`. If a token is exposed, revoke it in the UploadThing
dashboard and create a replacement before deploying.

For Render or Vercel, add the same three values in the project's environment
settings. The API accepts JPG, PNG, WebP, and GIF images up to 5MB, and PDF CVs
up to 10MB.
