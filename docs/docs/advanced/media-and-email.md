# Media, storage and email

**File/Image field contracts are bounded; storage and email integrations are
Evolving.** A file field stores a storage-relative reference in PostgreSQL.
The file bytes live in a separate storage backend. Sending an email is also an
external effect. Neither operation becomes atomic with a database transaction
merely because it is called while saving a model.

## Local storage and email check

The following complete script exercises local file storage and the in-memory
email backend. It needs no database, network service or credentials. Save it as
`check_media.py` in an environment with Aksara installed and run
`python check_media.py`.

```python title="check_media.py"
import asyncio
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

from aksara import fields, send_mail
from aksara.core.mail import outbox, reset_outbox
from aksara.storage import FileSystemStorage


async def main():
    checks = []
    with TemporaryDirectory(prefix="aksara-media-demo-") as directory:
        storage = FileSystemStorage(location=directory, base_url="/media/")
        # The application chooses the key; do not pass an untrusted path.
        name = await storage.save(f"reports/{uuid4().hex}.txt", b"ticket report")
        assert await storage.exists(name)
        checks.append("stored file exists")
        assert await storage.size(name) == len(b"ticket report")
        checks.append("stored byte count")
        handle = await storage.open(name)
        try:
            assert handle.read() == b"ticket report"
        finally:
            handle.close()
        checks.append("stored bytes round trip")
        assert Path(storage.path(name)).is_relative_to(Path(directory).resolve())
        checks.append("chosen key stays under temporary root")
        assert storage.url(name) == f"/media/{name}"
        checks.append("relative URL construction")
        await storage.delete(name)
        assert not await storage.exists(name)
        checks.append("explicit deletion")

    field = fields.FileField(allowed_extensions=["txt"])
    assert field.validate(("report.txt", b"ticket report"))
    checks.append("allowed upload name")
    try:
        field.validate(("../report.txt", b"ticket report"))
    except ValueError:
        checks.append("FileField rejects parent traversal")
    else:
        raise AssertionError("Unexpected FileField traversal acceptance")

    reset_outbox()
    sent = await send_mail("Report ready", "Download your report", None,
                           ["reader@example.com"], backend="locmem")
    assert sent == 1 and len(outbox) == 1
    assert outbox[0].subject == "Report ready"
    checks.append("in-memory email")
    reset_outbox()
    print(json.dumps({"pass": True, "checks": checks}))


if __name__ == "__main__":
    asyncio.run(main())
```

This checks the local primitives, not a protected upload API, database-backed
file lifecycle, SMTP delivery or S3 integration.

## File and image fields

```python
from aksara import Model, fields


class Asset(Model):
    name = fields.String(max_length=200)
    file = fields.FileField(upload_to="assets", allowed_extensions=["pdf"])
    preview = fields.ImageField(upload_to="previews", nullable=True)
```

Define the model in your application and generate/apply a migration before
using it. For an authenticated application that has already validated its input,
a `(filename, content)` tuple or supported `UploadFile` can be assigned to the
field before `await asset.save()`. An extension allowlist is not proof of content
safety; size, content handling and application upload policy still need review.

On a loaded instance, `asset.file` is a `FieldFile`. Its `name` is the stored
reference, `url` is a backend-generated URL and `path` is a local path when the
backend supports one. Async helpers include `exists()`, `size()`, `read()` and
`delete()`. Deletion removes the stored object and clears the in-memory reference;
it does not itself persist a database update. Do not treat file deletion or
replacement as reversible by rolling back PostgreSQL.

## Authorization and serving

An upload route must verify credentials, resolve the current Principal and
check permission for the target record before reading or changing its file.
Use tenant-aware queries and the same application policy as other writes. A
custom FastAPI route does not acquire those checks merely by using `Asset`.
The [ticket-desk authorization chapters](../tutorials/ticket-desk-tenancy.md)
show the application boundary; this page does not supply an upload API.

In debug mode, Aksara can mount filesystem storage at `media_url` (default
`/media/`). That static mount is not a per-record permission check. Do not place
private customer files behind a public static mount. Use an authenticated
application download route or an application-controlled limited-access delivery
mechanism, and back up the actual objects as well as their database references.

## Filesystem path limitation in v0.7.0

The direct `FileSystemStorage` path containment check uses a string prefix.
A key such as `../media-private/probe.txt` can resolve outside a root named
`media` into a sibling beginning with the same characters. This was reproduced
using two disposable directories; no application-data disclosure is claimed.

Do not pass caller-controlled keys to direct storage methods. Choose keys in
application code and validate names. `FileField` separately rejects `..` path
components, but that does not repair the backend's general containment check
or establish symlink safety. A separate runtime patch needs path-component and
symlink regression tests; this documentation release does not change it.

## Configuration and other backends

Use the [settings reference](../reference/settings-reference.md) for precedence
and exact storage/email variables. Configure filesystem storage before app startup:

```python
from aksara.conf import configure

configure(media_storage="filesystem", media_root="media", media_url="/media/")
```

S3-compatible storage requires the optional package extra:

```bash
python -m pip install "aksara-framework[s3]"
```

Configure the bucket, region and credentials for your deployment. A public base
URL is a delivery address, not an authorization mechanism. The local check above
does not certify an S3 service or bucket policy.

## Email delivery

`send_mail()` sends one message; `send_mass_mail()` sends batches. Available
backends include `console` (prints for development), `locmem` (process-local
outbox for tests) and `smtp` (uses `aiosmtplib`). The in-memory outbox is unrelated
to the durable Operation transition outbox and disappears with the process.

Use your secret store for SMTP credentials. Configure host, port, sender and
TLS according to the mail service; these are deployment settings, not a guarantee
of delivery. `backend="locmem"` in the script deliberately sends no real message.

For retryable notifications, ordinary tasks may be sufficient. For effects that
need persisted authorization and explicit uncertain-outcome handling, review
[Durable Operations](durable-operations.md#external-effects). A retry can duplicate
an external email; a PostgreSQL transaction cannot undo a message already sent.
