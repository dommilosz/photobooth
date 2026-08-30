# Nextcloud upload

This app uses the **File Request** public DAV API (verified on Nextcloud 32+).

## Share setup

1. Create a folder share with **Allow upload and editing** enabled.
2. Copy the share link into `upload.share_url` in config.
3. No password required for your current share.

## API

```
PUT https://<host>/public.php/dav/files/<token>/photo_01.jpg
Authorization: Basic <token>:
X-Requested-With: XMLHttpRequest
X-NC-Nickname: <session_id>
```

Session ID = `{event_name}_{YYYYMMDD_HHMMSS}`.

Files uploaded per session: `photo_01.jpg` … `photo_0N.jpg` + `sheet.jpg`.

Failed uploads are queued in `data/upload_queue/` and retried automatically.

Test from settings: **Test Nextcloud upload**.
