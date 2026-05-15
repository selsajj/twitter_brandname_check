# X Impersonation Scanner

Scans X (Twitter) for impersonation accounts of given handles.  
No X developer account or login required — uses Apify's free tier.

## Setup

```bash
# 1. Clone / enter the repo
cd x-impersonation-scanner

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure your API token
cp .env.example .env
# Edit .env and paste your Apify token

# 4. Add handles to scan
# Edit handles.txt or pass them inline (see Usage below)
```

## Usage

```bash
# Scan from file
python main.py handles.txt

# Scan inline handles
python main.py "elonmusk,nasa,bbcnews"

# Custom output name and options
python main.py handles.txt --output my_report --max-variants 30 --concurrency 3
```

## Output

Two files are created: `report.json` and `report.csv`  
Each row/entry contains:

| Field | Description |
|---|---|
| original_handle | The handle you provided |
| variant_handle | The generated impersonation variant |
| exists | Whether the account exists on X |
| name | Display name |
| follower_count | Number of followers |
| bio | Profile bio |
| created_at | Account creation date |
| verified | Whether the account is verified |
| recent_tweet_1–3 | Sample recent tweets |

## Free Tier Notes

Apify's free plan includes **$5/month** in credits.  
The actor used costs ~$0.001 per profile checked.  
With 50 variants per handle × 3 handles = 150 checks ≈ **$0.15** per run.
