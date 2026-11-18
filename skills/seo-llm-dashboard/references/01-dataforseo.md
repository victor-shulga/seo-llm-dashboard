# DataForSEO — the paid data layer

Everything that costs money in this stack is DataForSEO, pay-as-you-go. No subscription.
OpenSEO uses it for rank tracking, keyword data and backlinks; this skill's `scripts/avr.py` uses it for
live answers from ChatGPT, Gemini, Claude and Perplexity. The AI-only page needs DataForSEO and nothing else.

## Account

1. Sign up at app.dataforseo.com/register. New accounts get a $1 trial credit (dataforseo.com FAQ,
   checked November 2026): enough for `avr.py check`, not for a full run.
2. Top up by card. Minimum payment is $50 (dataforseo.com/help-center/minimum-payment); the balance does
   not expire. If the user asks about current terms, send them to dataforseo.com/pricing, do not quote
   from memory.
3. API access: app.dataforseo.com/api-access shows the API login and API password (NOT the dashboard
   password) and a **"Base64 Format"** field. That Base64 string is the key everywhere below:
   `base64(login:password)`, sent as `Authorization: Basic <key>`.

## Where the key goes (never print it, never commit it)

| Consumer | Where | How to set it |
|---|---|---|
| OpenSEO worker | Worker secret `DATAFORSEO_API_KEY` (exactly this name, not `DATAFORSEO_KEY`) | `npx wrangler secret put DATAFORSEO_API_KEY` in the open-seo repo, paste when prompted |
| `scripts/avr.py` (`dfs.py`) | first found of: env `DATAFORSEO_API_KEY` · env `DATAFORSEO_LOGIN` + `DATAFORSEO_PASSWORD` · .env file named by env `DATAFORSEO_ENV` · `~/.config/dataforseo/key` | simplest: `mkdir -p ~/.config/dataforseo && pbpaste > ~/.config/dataforseo/key && chmod 600 ~/.config/dataforseo/key` |

Secret hygiene (two-step rule): give the user one command that creates the file, and let them paste the
key themselves (`pbpaste`), so the key never passes through the chat.

## Smoke test ($0)

`python3 <skill-dir>/scripts/avr.py check` calls `GET /v3/appendix/user_data`, which is free, and prints
the login and balance. Run it on first use, before any estimate. (In the OpenSEO repo the same check is
`corepack pnpm billing:usage`.) A 401 means the key string is wrong (usually login:password pasted
instead of the Base64 field).

## What things cost (September 2026, observed)

| Action | Cost |
|---|---|
| One live LLM answer (`avr.py collect`, one cell) | ~$0.036-0.042 (Opus/Pro tier dearer than Sonar) |
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
