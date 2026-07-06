# Private podcast feed - one-time setup (~5 minutes)

Everything is built and wired. The only missing piece is a Cloudflare R2 bucket
(free tier: 10 GB storage, no bandwidth charges - this use case stays at £0).
Fill in four values and the feed goes live.

## 1. Create the R2 bucket

1. Sign up / log in at https://dash.cloudflare.com (free plan is fine).
2. In the left sidebar: **R2 Object Storage** -> **Create bucket**.
   - Name: `readaloud` (or anything - must match `bucket` in the config).
   - Location: Automatic. Cloudflare may ask for a payment card to activate
     R2; the free tier covers this usage, so expect £0.
3. Open the bucket -> **Settings** -> **Public access** ->
   **R2.dev subdomain** -> Enable.
   Copy the URL it shows, e.g. `https://pub-1a2b3c4d.r2.dev`.

## 2. Create an API token

1. R2 Object Storage -> **Manage R2 API Tokens** -> **Create API Token**.
2. Permissions: **Object Read & Write**, scoped to the `readaloud` bucket.
3. Copy three things from the confirmation screen:
   - Access Key ID
   - Secret Access Key
   - Endpoint, e.g. `https://<account-id>.r2.cloudflarestorage.com`

## 3. Fill in the config

Edit `podcast_config.json` (already created, gitignored; `token` is your
secret feed path - leave it as generated):

```json
{
  "base_url": "https://pub-1a2b3c4d.r2.dev",
  "endpoint_url": "https://<account-id>.r2.cloudflarestorage.com",
  "access_key_id": "...",
  "secret_access_key": "..."
}
```

## 4. Publish

```bash
./podcast-sync
```

This scans the iCloud ReadAloud folder (including MP3s exported from the app),
rebuilds `feed.xml`, uploads everything, and prints your feed URL:

```
https://pub-1a2b3c4d.r2.dev/<token>/feed.xml
```

From now on `./export <url>` publishes automatically; run `./podcast-sync`
after using the in-app Export button.

## 5. Follow it on your iPhone

Apple Podcasts -> **Library** -> **...** (top right) -> **Follow a Show by
URL...** -> paste the feed URL.

Episodes sync to Watch and CarPlay, keep playback position, and support speed
control like any podcast. Pull down on the show page to refresh after a new
export. (Spotify does not support external RSS feeds - Apple Podcasts,
Overcast, and Pocket Casts all do.)

## Privacy notes

- The feed URL contains a random secret token - anyone with the URL can
  listen, so don't share it. This feed is for YOUR listening only; audio of
  other people's articles must not be distributed.
- `<itunes:block>Yes</itunes:block>` is set, which tells Apple never to list
  the feed in the public directory even if the URL leaks.
- `podcast_config.json` holds the credentials and is gitignored.
