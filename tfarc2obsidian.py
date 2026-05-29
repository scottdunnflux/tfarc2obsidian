#!/usr/bin/env python3
"""Convert Tap Forms .tfarc backup files to Obsidian vaults."""

import argparse
import base64
import datetime
import json
import os
import pathlib
import re
import sys
import zipfile

# ---------------------------------------------------------------------------
# Phase 1: Archive Parsing and Schema Building
# ---------------------------------------------------------------------------

def parse_args():
    parser = argparse.ArgumentParser(
        description="Convert a Tap Forms .tfarc backup to an Obsidian vault."
    )
    parser.add_argument("tfarc_file", help="Path to the .tfarc backup file")
    parser.add_argument(
        "-o", "--output",
        help="Output directory (default: vault created next to input file)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be created without writing any files",
    )
    return parser.parse_args()


def load_archive(tfarc_path):
    path = pathlib.Path(tfarc_path)
    if not path.exists():
        sys.exit(f"Error: file not found: {tfarc_path}")
    try:
        zf = zipfile.ZipFile(path, "r")
    except zipfile.BadZipFile:
        sys.exit(f"Error: not a valid ZIP/tfarc file: {tfarc_path}")

    data_entry = None
    for name in zf.namelist():
        if name.endswith("/data.json"):
            data_entry = name
            break
    if data_entry is None:
        zf.close()
        sys.exit("Error: archive does not contain a data.json file")

    zip_prefix = data_entry.rsplit("/data.json", 1)[0]

    with zf.open(data_entry) as f:
        objects = json.load(f)

    return zf, objects, zip_prefix


def build_schema(objects):
    forms = {}
    fields_by_form = {}
    field_lookup = {}
    picklists = {}
    categories = {}
    records_by_form = {}

    for obj in objects:
        obj_type = obj.get("type", "")
        if obj_type == "TFForm":
            forms[obj["_id"]] = obj
        elif obj_type == "TFField":
            fid = obj["_id"]
            form_id = obj["form"]
            field_lookup[fid] = obj
            fields_by_form.setdefault(form_id, []).append(obj)
        elif obj_type == "TFPickList":
            picklists[obj["_id"]] = obj
        elif obj_type == "TFCategory":
            categories[obj["_id"]] = obj.get("name", "")
        elif obj_type.startswith("frm-"):
            records_by_form.setdefault(obj_type, []).append(obj)

    for form_id in fields_by_form:
        fields_by_form[form_id].sort(key=lambda f: f.get("sortOrder", 0))

    return {
        "forms": forms,
        "fields_by_form": fields_by_form,
        "field_lookup": field_lookup,
        "picklists": picklists,
        "categories": categories,
        "records_by_form": records_by_form,
    }


# ---------------------------------------------------------------------------
# Phase 2: Markdown Generation
# ---------------------------------------------------------------------------

_UNSAFE_CHARS = re.compile(r'[/\\:*?"<>|]')


def sanitize_filename(name, max_length=100):
    name = _UNSAFE_CHARS.sub("-", name)
    name = re.sub(r"\s+", " ", name).strip().strip(".")
    if len(name) > max_length:
        name = name[:max_length].rstrip()
    return name or "Untitled"


def slugify_field_name(name):
    slug = name.lower()
    slug = re.sub(r"[^a-z0-9\s_]", "", slug)
    slug = re.sub(r"\s+", "_", slug).strip("_")
    return slug or "field"


def _dedupe(slug, seen):
    original = slug
    counter = 2
    while slug in seen:
        slug = f"{original}_{counter}"
        counter += 1
    seen.add(slug)
    return slug


def get_record_title(record, form, fields):
    values = record.get("values", {})

    field_names = {f["_id"]: f["name"] for f in fields}
    first_name_id = None
    last_name_id = None
    for f in fields:
        if f["name"] == "First Name 1":
            first_name_id = f["_id"]
        if f["name"] == "Last Name":
            last_name_id = f["_id"]

    if first_name_id and last_name_id:
        first = str(values.get(first_name_id, "")).strip()
        last = str(values.get(last_name_id, "")).strip()
        combined = f"{first} {last}".strip()
        if combined:
            return combined

    sort_field = form.get("sortField1")
    if sort_field and sort_field in values:
        val = values[sort_field]
        if isinstance(val, str) and val.strip():
            return val.strip()

    for f in fields:
        if f.get("fieldType") == "text":
            val = values.get(f["_id"])
            if isinstance(val, str) and val.strip():
                return val.strip()

    return record.get("_id", "Untitled")


_YAML_SPECIAL = re.compile(r'[:#\[\]{},%&*!|>\'"@`]')


def yaml_quote(value):
    s = str(value)
    if (
        _YAML_SPECIAL.search(s)
        or s.startswith("- ")
        or s.startswith("? ")
        or s.lower() in ("true", "false", "null", "yes", "no", "on", "off")
        or s == ""
    ):
        escaped = s.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    try:
        float(s)
        return f'"{s}"'
    except ValueError:
        pass
    return s


def format_frontmatter_value(value, field_type):
    if field_type in ("text", "phone", "email", "web_site", "contact"):
        return yaml_quote(str(value))
    if field_type == "number":
        if isinstance(value, (int, float)):
            return value
        return yaml_quote(str(value))
    if field_type == "date":
        if isinstance(value, dict) and "date" in value:
            try:
                dt = datetime.datetime.fromisoformat(
                    value["date"].replace("Z", "+00:00")
                )
                return dt.strftime("%Y-%m-%d")
            except (ValueError, AttributeError):
                return yaml_quote(str(value["date"]))
        return yaml_quote(str(value))
    if field_type == "check_mark":
        if isinstance(value, str):
            return "true" if value.lower() == "true" else "false"
        return "true" if value else "false"
    return yaml_quote(str(value))


def build_yaml_frontmatter(record, form, fields):
    values = record.get("values", {})
    lines = ["---"]

    lines.append(f"form: {yaml_quote(form['name'])}")

    tag = re.sub(r"[^a-z0-9-]", "-", form["name"].lower())
    tag = re.sub(r"-+", "-", tag).strip("-")
    lines.append("tags:")
    lines.append(f"  - {tag}")

    seen_slugs = set()
    for field in fields:
        ftype = field.get("fieldType", "")
        if ftype in ("note", "photo"):
            continue
        fid = field["_id"]
        val = values.get(fid)
        if val is None or val == "":
            continue
        slug = slugify_field_name(field["name"])
        slug = _dedupe(slug, seen_slugs)
        formatted = format_frontmatter_value(val, ftype)
        lines.append(f"{slug}: {formatted}")

    date_created = record.get("dateCreated", "")
    date_modified = record.get("dateModified", "")
    if date_created:
        try:
            dt = datetime.datetime.fromisoformat(
                date_created.replace("Z", "+00:00")
            )
            lines.append(f"date_created: {dt.strftime('%Y-%m-%d')}")
        except ValueError:
            lines.append(f"date_created: {yaml_quote(date_created)}")
    if date_modified:
        try:
            dt = datetime.datetime.fromisoformat(
                date_modified.replace("Z", "+00:00")
            )
            lines.append(f"date_modified: {dt.strftime('%Y-%m-%d')}")
        except ValueError:
            lines.append(f"date_modified: {yaml_quote(date_modified)}")

    lines.append("---")
    return "\n".join(lines)


def build_markdown_body(record, fields, attachment_filenames):
    sections = []

    if attachment_filenames:
        for fname in attachment_filenames:
            sections.append(f"![[{fname}]]")
        sections.append("")

    values = record.get("values", {})
    for field in fields:
        if field.get("fieldType") != "note":
            continue
        fid = field["_id"]
        val = values.get(fid)
        if not val or not str(val).strip():
            continue
        sections.append(f"## {field['name']}")
        sections.append("")
        sections.append(str(val).strip())
        sections.append("")

    return "\n".join(sections)


def generate_all_markdown(schema):
    results = []

    for form_id, form in schema["forms"].items():
        form_name = form["name"]
        fields = schema["fields_by_form"].get(form_id, [])
        records = schema["records_by_form"].get(form_id, [])

        title_counts = {}
        for record in records:
            title = get_record_title(record, form, fields)
            safe_title = sanitize_filename(title)
            title_counts.setdefault(safe_title, []).append(record)

        for safe_title, recs in title_counts.items():
            for i, record in enumerate(recs):
                if len(recs) > 1:
                    file_title = f"{safe_title} {i + 1}" if i > 0 else safe_title
                    if i == 0 and len(recs) > 1:
                        file_title = safe_title
                else:
                    file_title = safe_title

                if len(recs) > 1 and i > 0:
                    file_title = f"{safe_title} {i + 1}"

                rel_path = f"{form_name}/{file_title}.md"

                attachments = record.get("_attachments", {})
                attachment_filenames = []
                attachment_info = {}
                for orig_name, meta in attachments.items():
                    if orig_name == "icon":
                        continue
                    clean_name = sanitize_filename(orig_name)
                    if not clean_name or clean_name == "Untitled":
                        ext = _ext_from_content_type(meta.get("content_type", ""))
                        clean_name = f"attachment{ext}"
                    attachment_filenames.append(clean_name)
                    digest = meta.get("digest", "")
                    attachment_info[clean_name] = {
                        "digest": digest,
                        "original_name": orig_name,
                        "content_type": meta.get("content_type", ""),
                        "size": meta.get("length", 0),
                    }

                frontmatter = build_yaml_frontmatter(record, form, fields)
                body = build_markdown_body(record, fields, attachment_filenames)
                content = frontmatter + "\n" + body
                if not content.endswith("\n"):
                    content += "\n"

                results.append((rel_path, content, attachment_info))

    return results


def _ext_from_content_type(ct):
    mapping = {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/tiff": ".tiff",
        "image/gif": ".gif",
        "application/pdf": ".pdf",
    }
    return mapping.get(ct, "")


# ---------------------------------------------------------------------------
# Phase 3: Attachment Extraction
# ---------------------------------------------------------------------------

def digest_to_blob_path(digest_str, zip_prefix):
    if not digest_str.startswith("sha1-"):
        return None
    b64 = digest_str[5:]
    try:
        raw = base64.b64decode(b64)
    except Exception:
        return None
    hex_hash = raw.hex().upper()
    return f"{zip_prefix}/attachments/{hex_hash}.blob"


def plan_attachment_extraction(schema, zip_prefix):
    plan = []
    folder_names_used = {}

    for form_id, form in schema["forms"].items():
        form_name = form["name"]
        records = schema["records_by_form"].get(form_id, [])
        names_in_folder = folder_names_used.setdefault(form_name, set())

        for record in records:
            attachments = record.get("_attachments", {})
            for orig_name, meta in attachments.items():
                if orig_name == "icon":
                    continue
                digest = meta.get("digest", "")
                blob_path = digest_to_blob_path(digest, zip_prefix)
                if blob_path is None:
                    continue

                clean_name = sanitize_filename(orig_name)
                if not clean_name or clean_name == "Untitled":
                    ext = _ext_from_content_type(meta.get("content_type", ""))
                    clean_name = f"attachment{ext}"

                base, ext = os.path.splitext(clean_name)
                final_name = clean_name
                counter = 2
                while final_name in names_in_folder:
                    final_name = f"{base}_{counter}{ext}"
                    counter += 1
                names_in_folder.add(final_name)

                plan.append({
                    "blob_zip_path": blob_path,
                    "output_relative_path": f"{form_name}/_attachments/{final_name}",
                    "original_filename": orig_name,
                    "content_type": meta.get("content_type", ""),
                    "size": meta.get("length", 0),
                })

    return plan


def extract_attachments(zf, extraction_plan, output_dir, dry_run=False):
    total = len(extraction_plan)
    if total == 0:
        return

    zip_entries = set(zf.namelist())
    extracted = 0
    skipped = 0
    total_bytes = 0

    for i, item in enumerate(extraction_plan):
        blob_path = item["blob_zip_path"]
        out_rel = item["output_relative_path"]
        out_path = output_dir / out_rel

        if blob_path not in zip_entries:
            print_progress(f"  Warning: blob not found: {blob_path}", file=sys.stderr)
            skipped += 1
            continue

        if dry_run:
            extracted += 1
            continue

        out_path.parent.mkdir(parents=True, exist_ok=True)
        with zf.open(blob_path) as src, open(out_path, "wb") as dst:
            while True:
                chunk = src.read(1024 * 1024)
                if not chunk:
                    break
                dst.write(chunk)

        total_bytes += item["size"]
        extracted += 1

        if (i + 1) % 20 == 0 or (i + 1) == total:
            mb = total_bytes / (1024 * 1024)
            print_progress(
                f"  Attachments: {i + 1}/{total} ({mb:.0f} MB extracted)"
            )

    if skipped:
        print_progress(f"  Warning: {skipped} attachment(s) could not be found")


# ---------------------------------------------------------------------------
# Phase 4: Output Writing and CLI
# ---------------------------------------------------------------------------

def print_progress(message, file=None):
    print(message, file=file or sys.stderr, flush=True)


def build_template(form, fields):
    lines = ["---"]
    lines.append(f"form: {yaml_quote(form['name'])}")

    tag = re.sub(r"[^a-z0-9-]", "-", form["name"].lower())
    tag = re.sub(r"-+", "-", tag).strip("-")
    lines.append("tags:")
    lines.append(f"  - {tag}")

    seen_slugs = set()
    note_fields = []
    has_photo_fields = False
    for field in fields:
        ftype = field.get("fieldType", "")
        if ftype == "note":
            note_fields.append(field)
            continue
        if ftype == "photo":
            has_photo_fields = True
            continue
        slug = slugify_field_name(field["name"])
        slug = _dedupe(slug, seen_slugs)
        if ftype == "check_mark":
            lines.append(f"{slug}: false")
        else:
            lines.append(f"{slug}: ")

    lines.append("date_created: \"{{date:YYYY-MM-DD}}\"")
    lines.append("date_modified: \"{{date:YYYY-MM-DD}}\"")
    lines.append("---")

    body_parts = []
    if has_photo_fields:
        body_parts.append("")
        body_parts.append("<!-- Attach images: drag into _attachments folder, then embed with ![[filename.jpg]] -->")

    for field in note_fields:
        body_parts.append("")
        body_parts.append(f"## {field['name']}")
        body_parts.append("")

    lines.extend(body_parts)
    lines.append("")
    return "\n".join(lines)


def write_templates(schema, output_dir):
    templates_dir = output_dir / "Templates"
    templates_dir.mkdir(parents=True, exist_ok=True)
    for form_id, form in schema["forms"].items():
        fields = schema["fields_by_form"].get(form_id, [])
        content = build_template(form, fields)
        path = templates_dir / f"{form['name']}.md"
        path.write_text(content, encoding="utf-8")


def write_index_note(form_name, record_titles, output_dir):
    titles_sorted = sorted(record_titles, key=lambda t: t.lower())
    lines = [f"# {form_name}", "", f"*{len(titles_sorted)} records*", ""]
    for title in titles_sorted:
        lines.append(f"- [[{title}]]")
    lines.append("")

    path = output_dir / form_name / "_Index.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_vault_readme(output_dir, schema):
    lines = [f"# {output_dir.name}", ""]
    lines.append(
        f"Converted from Tap Forms backup on "
        f"{datetime.date.today().isoformat()}."
    )
    lines.append("")
    lines.append("| Form | Records |")
    lines.append("|------|---------|")
    for form_id, form in sorted(
        schema["forms"].items(), key=lambda x: x[1]["name"]
    ):
        name = form["name"]
        count = len(schema["records_by_form"].get(form_id, []))
        lines.append(f"| [[{name}/_Index\\|{name}]] | {count} |")
    lines.append("")

    lines.append("## Creating new records")
    lines.append("")
    lines.append(
        "This vault includes templates for each form in the `Templates/` folder."
    )
    lines.append("")
    lines.append("To use them with Obsidian's built-in Templates plugin:")
    lines.append("")
    lines.append(
        "1. Go to **Settings → Core Plugins** and enable **Templates**"
    )
    lines.append(
        "2. Go to **Settings → Templates** and set "
        '"Template folder location" to `Templates`'
    )
    lines.append(
        "3. Create a new note in the form folder you want "
        "(e.g., `Home Inventory/`)"
    )
    lines.append(
        "4. Press **Cmd-P**, type **Insert template**, "
        "and select the matching form template"
    )
    lines.append("")

    path = output_dir / "README.md"
    path.write_text("\n".join(lines), encoding="utf-8")


def write_vault(output_dir, markdown_files, extraction_plan, zf, schema, dry_run=False):
    if not dry_run:
        output_dir.mkdir(parents=True, exist_ok=True)

    print_progress(f"  Writing {len(markdown_files)} markdown files...")
    form_record_titles = {}
    for rel_path, content, _ in markdown_files:
        parts = rel_path.split("/", 1)
        form_name = parts[0]
        file_title = parts[1].rsplit(".md", 1)[0] if len(parts) > 1 else "Untitled"
        form_record_titles.setdefault(form_name, []).append(file_title)

        if not dry_run:
            full_path = output_dir / rel_path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(content, encoding="utf-8")

    print_progress(f"  Extracting {len(extraction_plan)} attachments...")
    extract_attachments(zf, extraction_plan, output_dir, dry_run=dry_run)

    print_progress("  Writing index notes and templates...")
    if not dry_run:
        for form_name, titles in form_record_titles.items():
            write_index_note(form_name, titles, output_dir)
        write_templates(schema, output_dir)

    return form_record_titles


def main():
    args = parse_args()

    print_progress("Loading archive...")
    zf, objects, zip_prefix = load_archive(args.tfarc_file)

    print_progress("Building schema...")
    schema = build_schema(objects)

    form_count = len(schema["forms"])
    record_count = sum(len(r) for r in schema["records_by_form"].values())
    field_count = sum(len(f) for f in schema["fields_by_form"].values())
    print_progress(
        f"  Found {form_count} forms, {field_count} fields, "
        f"{record_count} records"
    )

    print_progress("Generating markdown...")
    markdown_files = generate_all_markdown(schema)

    extraction_plan = plan_attachment_extraction(schema, zip_prefix)

    if args.output:
        output_dir = pathlib.Path(args.output)
    else:
        vault_name = zip_prefix
        output_dir = pathlib.Path(args.tfarc_file).parent / vault_name

    if output_dir.exists() and not args.dry_run:
        sys.exit(
            f"Error: output directory already exists: {output_dir}\n"
            f"Use -o to specify a different output path, or remove the "
            f"existing directory."
        )

    if args.dry_run:
        print_progress(f"\n--- Dry Run ---")
        print_progress(f"Would create vault at: {output_dir}")
        print_progress(f"  {len(markdown_files)} markdown files")
        print_progress(f"  {len(extraction_plan)} attachment files")
        forms_shown = set()
        for rel_path, _, _ in markdown_files:
            form = rel_path.split("/")[0]
            if form not in forms_shown:
                count = sum(
                    1 for r, _, _ in markdown_files if r.startswith(form + "/")
                )
                att_count = sum(
                    1
                    for a in extraction_plan
                    if a["output_relative_path"].startswith(form + "/")
                )
                print_progress(
                    f"    {form}: {count} records, {att_count} attachments"
                )
                forms_shown.add(form)
        zf.close()
        return

    print_progress(f"\nWriting vault to: {output_dir}")
    form_record_titles = write_vault(
        output_dir, markdown_files, extraction_plan, zf, schema, dry_run=False
    )

    write_vault_readme(output_dir, schema)

    zf.close()

    template_count = len(schema["forms"])
    total_files = len(markdown_files) + len(extraction_plan)
    index_count = len(form_record_titles)
    print_progress(
        f"\nDone! Created {total_files + index_count + template_count + 1} files in {output_dir}"
    )
    print_progress(f"  {len(markdown_files)} records")
    print_progress(f"  {len(extraction_plan)} attachments")
    print_progress(f"  {index_count} index notes")
    print_progress(f"  {template_count} templates")
    print_progress(f"  1 README")


if __name__ == "__main__":
    main()
