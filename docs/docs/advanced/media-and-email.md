# Media and Email

Phase 3 adds two framework-level primitives that most real applications need:
storage-backed file fields and async email delivery.

---

## File and Image Fields

`FileField` and `ImageField` store a storage-relative path in PostgreSQL while
exposing a `FieldFile` helper on model instances.

```python
from aksara import Model, fields


class Asset(Model):
    name = fields.String(max_length=200)
    file = fields.FileField(upload_to="assets")
    preview = fields.ImageField(upload_to="previews", nullable=True)
```

### Saving Upload Content

You can assign a tuple of `(filename, content)` directly:

```python
asset = Asset(name="Quarterly Report")
asset.file = ("q1-report.pdf", pdf_bytes)
await asset.save()
```

For FastAPI uploads, pass the incoming `UploadFile` straight to the model:

```python
from aksara import Aksara, UploadFile

app = Aksara(database_url="postgresql://localhost/myapp")


@app.post("/assets/{asset_id}/upload")
async def upload_asset(asset_id: str, file: UploadFile):
    asset = await Asset.objects.get(id=asset_id)
    asset.file = file
    await asset.save()
    return {"file": asset.file.url}
```

### Working with FieldFile

```python
asset = await Asset.objects.get(id=asset_id)

asset.file.url
asset.file.path
await asset.file.exists()
await asset.file.size()
await asset.file.read()
await asset.file.delete()
```

---

## Storage Backends

### Local Filesystem

```python
from aksara.conf import configure

configure(
    media_storage="filesystem",
    media_root="media",
    media_url="/media/",
)
```

In debug mode, Aksara mounts `MEDIA_URL` automatically when filesystem storage
is active.

### S3-Compatible Storage

```python
configure(
    media_storage="s3",
    media_s3_bucket="my-app-media",
    media_s3_region="us-east-1",
    media_public_base_url="https://cdn.example.com/media",
)
```

Install the optional dependency when using S3-compatible storage:

```bash
pip install "aksara-framework[s3]"
```

---

## Async Email

Use `send_mail()` for one-off notifications or `send_mass_mail()` for batches.

```python
from aksara import send_mail

await send_mail(
    "Welcome to Aksara",
    "Your account is ready.",
    None,
    ["user@example.com"],
)
```

### Backends

- `console`: prints emails to stdout for development
- `locmem`: stores emails in memory for tests
- `smtp`: sends via SMTP with `aiosmtplib`

### SMTP Configuration

```python
import os

configure(
    email_backend="smtp",
    default_from_email="noreply@example.com",
    email_host="smtp.example.com",
    email_port=587,
    email_host_user="mailer",
    email_host_password=os.environ["AKSARA_EMAIL_HOST_PASSWORD"],
    email_use_tls=True,
)
```

### HTML Messages

```python
await send_mail(
    "Password Reset",
    "Use the link below to reset your password.",
    None,
    ["user@example.com"],
    html_message="<p>Use the link below to reset your password.</p>",
)
```

---

## Testing

Use the in-memory backend for deterministic test assertions:

```python
from aksara.conf import configure
from aksara.core.mail import outbox, reset_outbox

configure(email_backend="locmem")
reset_outbox()

await send_mail("Subject", "Body", None, ["user@example.com"])
assert len(outbox) == 1
assert outbox[0].subject == "Subject"
```