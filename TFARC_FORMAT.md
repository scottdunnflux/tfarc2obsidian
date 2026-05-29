# .tfarc File Format Specification

This document describes the internal structure of `.tfarc` files produced by [Tap Forms 5](https://www.tapforms.com) for macOS and iOS. It was reverse-engineered by examining sample backup files and is not based on official documentation. The findings here are accurate for Tap Forms 5 backups produced as of 2025, but may not cover every edge case or future format changes.

## Overview

A `.tfarc` file is a **standard ZIP archive** (detectable via the `PK` magic bytes). It contains a single top-level directory whose name matches the backup name, with two components inside:

```
<Backup Name>/
  data.json
  attachments/
    <HEX_SHA1>.blob
    <HEX_SHA1>.blob
    ...
```

- **`data.json`** — A single JSON array containing every object in the database: forms, fields, records, pick lists, categories, and layouts. Typically a few megabytes even for large databases.
- **`attachments/`** — Binary files (photos, icons) named by their SHA-1 hash in uppercase hex, with a `.blob` extension. This is where the bulk of the file size lives.

The top-level directory name is not fixed — it is derived from the database name and backup date (e.g., `Sample Forms 1 2026-05-25`). Consumers should discover it dynamically by searching for the entry ending in `/data.json`.

## data.json Structure

The file contains a flat JSON array of objects. Every object has at minimum:

```json
{
  "_id": "unique-identifier",
  "type": "object-type",
  "dbID": "db-...",
  "_rev": "revision-string",
  "_revisions": "comma-separated-revision-history"
}
```

The `_id` prefix indicates the object type:

| Prefix | Type |
|--------|------|
| `cat-` | TFCategory |
| `frm-` | TFForm |
| `fld-` | TFField |
| `pik-` | TFPickList |
| `lay-` | TFFormLayout |
| `rec-` | Record (but see note below) |

The `type` field contains the object's type name for schema objects, or the **form's `_id`** for data records.

### Object Types

#### TFCategory

Groups forms into categories (e.g., "Personal", "Business").

```json
{
  "_id": "cat-5d5d159da4e74673a1da2bf4643e3d7b",
  "type": "TFCategory",
  "name": "Personal",
  "sortOrder": 0
}
```

#### TFForm

Defines a form (equivalent to a table or collection).

```json
{
  "_id": "frm-9f5d1d4ffd9a40788b835d99b2b052e3",
  "type": "TFForm",
  "name": "Bank Accounts",
  "formCategory": "cat-...",
  "sortField1": "fld-...",
  "sortField1Direction": "asc",
  "sortOrder": 0,
  "shouldSync": true,
  "listViewFieldsCount": 2,
  "_attachments": {
    "icon": { "stub": true, "digest": "sha1-...", "content_type": "image/png", "length": 6863 }
  }
}
```

Key fields:
- `name` — The user-visible form name
- `formCategory` — References a TFCategory `_id`
- `sortField1` — The `_id` of the field used as the default sort / display title
- `_attachments.icon` — The form's icon image (see Attachments section)

#### TFField

Defines a field (column) within a form.

```json
{
  "_id": "fld-536577fa24cc421cad65c3ba84f6afe4",
  "type": "TFField",
  "form": "frm-9f5d1d4ffd9a40788b835d99b2b052e3",
  "name": "Bank Name",
  "fieldType": "text",
  "sortOrder": 0,
  "multiEnabled": false,
  "shouldExport": 1,
  "shouldEmail": 1,
  "shouldPrint": 1,
  "jsonParameterName": "bank_name"
}
```

Key fields:
- `form` — References the parent TFForm `_id`
- `fieldType` — The data type (see Field Types below)
- `sortOrder` — Display order within the form
- `jsonParameterName` — An optional export key name

##### Field Types

| `fieldType` | Value stored in record `values` dict | Notes |
|------------|--------------------------------------|-------|
| `text` | `"string"` | General text, also used for pick list selections |
| `number` | `123` or `45.67` | Native JSON number (int or float), no currency formatting |
| `date` | `{"date": "2027-08-01T07:00:00.000Z"}` | Object with ISO 8601 timestamp string |
| `check_mark` | `"True"` or `"False"` | String values, not JSON booleans |
| `phone` | `"(509) 754-2977"` | Formatted phone string |
| `email` | `"user@example.com"` | Email string |
| `web_site` | `"example.com"` | URL string |
| `note` | `"Long text content..."` | May contain newlines; can be multiline |
| `contact` | Unknown | Present in field definitions but unpopulated in sample data |
| `photo` | Not stored in `values` | Photos are in the record's `_attachments` dict |

Additional field properties of interest:
- `isMasked` — If true, the field is a sensitive value (e.g., account numbers)
- `pickListColumns` — Number of columns in pick list display
- `autoIncrement` / `incrementAmount` — Auto-numbering configuration
- `formulaReturnType` — Used for calculated fields

#### TFPickList

Reusable sets of values for dropdown/selection fields.

```json
{
  "_id": "pik-74d47fe7a4bc448b9a813c0857296f01",
  "type": "TFPickList",
  "name": "Condition",
  "displayMode": "single",
  "items": ["Excellent", "Fair", "Good", "Poor"]
}
```

The selected value is stored as a plain string in the record's `values` dict — there is no ID reference back to the pick list.

#### TFFormLayout

Print/layout configuration for a form. Contains properties like `orientation`, `labelWidth`, `labelHeight`, etc. Not relevant for data extraction.

### Data Records

Records have `type` set to their parent form's `_id` (e.g., `"type": "frm-8208c5952882492d9a9618e1f8a4514a"`). This is how records are associated with forms.

```json
{
  "_id": "rec-a1b2c3d4...",
  "type": "frm-8208c5952882492d9a9618e1f8a4514a",
  "form": "frm-8208c5952882492d9a9618e1f8a4514a",
  "dbID": "db-...",
  "dateCreated": "2022-06-06T21:34:46.000Z",
  "dateModified": "2024-06-12T23:26:40.123Z",
  "deviceName": "User's Computer",
  "values": {
    "fld-abc123": "Watch - Casio",
    "fld-def456": 48.43,
    "fld-ghi789": {"date": "2022-06-03T07:00:00.000Z"},
    "fld-jkl012": "True"
  },
  "_attachments": {
    "Watch Casio.JPG": {
      "stub": true,
      "length": 93091,
      "digest": "sha1-QwlkyKNxl7M8Gve3YZR5Vn9qe+U=",
      "revpos": 4,
      "content_type": "image/jpeg"
    }
  }
}
```

Key fields:
- `type` and `form` — Both reference the parent form's `_id`
- `dateCreated` / `dateModified` — ISO 8601 timestamps with milliseconds
- `values` — Dict mapping field `_id` to the stored value (see Field Types above)
- `_attachments` — Dict mapping original filenames to attachment metadata (see Attachments below)
- `oldPK` — Legacy primary key from earlier versions or imports (e.g., `lib_contacts:UUID` for imported Apple Contacts)

#### The `-attr` key pattern

The `values` dict may contain keys suffixed with `-attr` (e.g., `"fld-abc123-attr": <binary data>`). These are **NSKeyedArchiver binary plist blobs** encoding rich text formatting (fonts, colors, etc.) for note fields. The plain text content is in the base key (`fld-abc123`); the `-attr` variant can be safely ignored for data extraction purposes.

## Attachments

### Storage

Attachment files are stored in the `attachments/` directory within the ZIP, named by their SHA-1 content hash in uppercase hexadecimal with a `.blob` extension:

```
attachments/7D71A26E17F6A04B28D5C27A6010FC6FC8574BE1.blob
```

The files are the raw binary content (JPEG, PNG, TIFF, etc.) — the `.blob` extension is just a naming convention.

### Digest Mapping

Each attachment reference includes a `digest` field in the format:

```
sha1-<base64-encoded-SHA1>
```

To find the corresponding blob file:

1. Strip the `sha1-` prefix
2. Base64-decode the remaining string (produces 20 raw bytes)
3. Convert to uppercase hexadecimal (40 characters)
4. The blob file is at `<zip_prefix>/attachments/<HEX>.blob`

Example:
```
digest: "sha1-fXGibhf2oEso1cJ6YBD8b8hXS+E="
         ↓ base64 decode
bytes:   7d 71 a2 6e 17 f6 a0 4b 28 d5 c2 7a 60 10 fc 6f c8 57 4b e1
         ↓ hex encode
path:    attachments/7D71A26E17F6A04B28D5C27A6010FC6FC8574BE1.blob
```

### Attachment Contexts

Attachments appear in two contexts:

1. **Form icons** — On TFForm objects under `_attachments["icon"]`. These are small PNG images used as the form's icon in the Tap Forms UI.

2. **Record photos** — On data records under `_attachments["original_filename.jpg"]`. The dict key is the **original filename** as captured by Tap Forms (e.g., `"IMG_1094.jpeg"`, `"4 Wheel Dolly.jpg"`).

### Content Types Observed

| MIME type | Frequency |
|-----------|-----------|
| `image/jpeg` | ~96.5% |
| `image/png` | ~2.2% |
| `image/tiff` | ~1.3% |

### Multiple Attachments

A single record may have multiple attachments (observed up to 3 per record), each as a separate key in the `_attachments` dict. This is uncommon (~1.3% of records).

## CouchDB Heritage

The schema shows clear CouchDB / PouchDB lineage:

- `_id`, `_rev`, `_revisions` — Standard CouchDB document fields
- `_attachments` with `stub`, `digest`, `revpos` — CouchDB attachment stubs
- The `sha1-<base64>` digest format is CouchDB's default

This suggests Tap Forms uses an embedded CouchDB-compatible database internally, and the `.tfarc` export serializes it to a flat JSON array with attachment blobs extracted to files.

## Sample Statistics

From a real-world database backup (1.1 GB total):

| Component | Count | Size |
|-----------|-------|------|
| data.json | 803 objects | 2.1 MB |
| Attachment blobs | 618 files | 1,095 MB |
| Forms | 7 | — |
| Fields | 96 | — |
| Records | 695 | — |
| Pick lists | 3 | — |
| Categories | 1 | — |

Data integrity was perfect: every digest in data.json mapped to a blob in the ZIP, and every blob in the ZIP was referenced by a digest. No orphans in either direction.
