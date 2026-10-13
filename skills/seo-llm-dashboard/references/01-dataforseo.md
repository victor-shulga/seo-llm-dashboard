# DataForSEO — the paid data layer

Everything that costs money in this stack is DataForSEO, pay-as-you-go. No subscription.
OpenSEO uses it for rank tracking, keyword data and backlinks; ai-visibility-report uses it for
live answers from ChatGPT, Gemini, Claude and Perplexity.

## Account

1. Sign up at app.dataforseo.com (business email works; you get a small trial balance).
2. Top up (card). $20-50 covers months of this dashboard.
3. API access: app.dataforseo.com/api-access. Copy the value from the **"Base64 Format"** field.
   That string is the key everywhere below. It is `base64(login:password)`, sent as `Authorization: Basic <key>`.

## Where the key goes (never print it, never commit it)

| Consumer | Where | How to set it |
|---|---|---|
| OpenSEO worker | Worker secret `DATAFORSEO_API_KEY` (exactly this name, not `DATAFORSEO_KEY`) | `npx wrangler secret put DATAFORSEO_API_KEY` in the open-seo repo, paste when prompted |
| ai-visibility-report (`dfs.py`) | first found of: env `DATAFORSEO_API_KEY` · file named by env `DATAFORSEO_ENV` · OpenSEO `.env.local` · `~/.config/dataforseo/key` | simplest: `mkdir -p ~/.config/dataforseo && pbpaste > ~/.config/dataforseo/key && chmod 600 ~/.config/dataforseo/key` |

Secret hygiene (two-step rule): give the user one command that creates the file, and let them paste the
key themselves (`pbpaste`), so the key never passes through the chat.

## Smoke test ($0)

`GET /v3/appendix/user_data` is free and returns balance and spend. In the OpenSEO repo:
`corepack pnpm billing:usage`. A 401 means the key string is wrong (usually login:password pasted
instead of the Base64 field).

## What things cost (September 2026, observed)

| Action | Cost |
|---|---|
| One live LLM answer (ai-visibility-report cell) | ~$0.036-0.042 (Opus/Pro tier dearer than Sonar) |
| 27 prompts x 4 models = 108 answers | $4.33 |
| 16 prompts x 4 models = 64 answers | $2.31 |
| AI keyword search volume, one call | cents |
| Rank check, 10-12 keywords, one domain | ~$0.08 per check (OpenSEO schedules it weekly) |
| Live SERP, 5 queries | ~$0.02 |

Failed tasks are not billed (e.g. a rejected country code costs $0).

## Locale support worth knowing

- `web_search_country_iso_code` for live LLM answers: ChatGPT and Perplexity accept `UA`; Claude rejects
  it (`40501 Invalid Field`); Gemini takes no country at all. For non-US markets put the country into the
  prompt text too ("…in Ukraine").
- AI keyword volume (`ai_keyword_data`) returns numbers for Ukraine, but long-tail phrasings are 0 (below
  the dataset threshold). Pass short head terms to get anything.
- DataForSEO Labs keyword suggestions are empty for small non-US niches; seed rank-tracking keywords by hand
  (Gemini's "Related queries the model considered" block is a free source of real phrasings).
