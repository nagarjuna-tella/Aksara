# Admin Widgets

Widgets control how fields render on admin add/change forms. Aksara includes
standard field rendering plus dedicated widgets for JSON and array-style fields.

---

## Built-in Structured Widgets

JSON and array fields receive dedicated widgets automatically when the admin can
infer the field type. You can also configure them explicitly through
`formfield_overrides`.

```python
from aksara.contrib.admin import ModelAdmin
from aksara.contrib.admin.widgets import ArrayAdminWidget, JSONAdminWidget

class ProductAdmin(ModelAdmin):
    formfield_overrides = {
        "metadata": JSONAdminWidget(rows=16),
        "tags": ArrayAdminWidget(item_type="text", min_rows=1, max_rows=20),
    }
```

---

## JSONAdminWidget

`JSONAdminWidget` renders a monospace textarea for JSON data, pretty-prints the
initial value when possible, and includes a client-side format button.

```python
JSONAdminWidget(rows=12, pretty_print=True)
```

Submitted values are parsed by the admin form handling before save. Invalid JSON
is surfaced as a form error rather than silently accepted.

---

## ArrayAdminWidget

`ArrayAdminWidget` renders repeatable rows for list-like values and serializes
the submitted list into the hidden form field used by the admin save path.

```python
ArrayAdminWidget(item_type="text", min_rows=1, max_rows=20)
```

Supported `item_type` values are regular HTML input types such as:

- `"text"`
- `"number"`
- `"email"`
- `"url"`

---

## Standard Form Rendering

For ordinary fields, the admin maps model fields to standard HTML controls:

| Model field | Form control |
|-------------|--------------|
| string/email/url | text-like input |
| text/json | textarea or JSON widget |
| integer/float/decimal | number input |
| boolean | checkbox |
| date/time/datetime | date/time input |
| foreign key | select or raw id input |
| many-to-many | multi-select |

Boolean values are preserved for checkbox rendering, so saved `False` values
render unchecked.

---

## Related Documentation

- [ModelAdmin](model-admin.md) — Form layout and `formfield_overrides`
- [Admin Permissions](admin-permissions.md) — Field visibility and readonly hooks
