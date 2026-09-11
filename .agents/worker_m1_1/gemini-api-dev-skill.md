# Local Dump: gemini-api-dev skill
Source: C:\Users\jacob\.gemini\config\plugins\gemini-api\skills\gemini-api-dev\SKILL.md

Current Models:
- gemini-2.5-flash-lite, gemini-2.0-flash-lite (Flash Lite models)
- gemini-2.5-flash, gemini-3.7-flash

SDK:
- Python: google-genai (`from google import genai`, `from google.genai import types`)
- Client: `client = genai.Client(api_key=...)`
- Sync: `client.models.generate_content(model=..., contents=..., config=...)`
- Async: `await client.aio.models.generate_content(...)`
- Async Stream: `await client.aio.models.generate_content_stream(...)`
- Token count: `client.models.count_tokens(...)`
