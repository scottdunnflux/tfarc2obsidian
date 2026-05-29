# tfarc2obsidian

## A new life for your Tap Forms data

If you've used [Tap Forms](https://www.tapforms.com) on your Mac to organize contacts, home inventory, bank accounts, insurance policies, or anything else — and you're looking for a way to keep using that data going forward — this tool is for you.

**tfarc2obsidian** converts a Tap Forms backup file (`.tfarc`) into an [Obsidian](https://obsidian.md) vault: a folder of simple, readable files that you own and control, with all your records, notes, and photos intact.

### Who is this for?

Long-time Tap Forms users on macOS who want to:

- Access their data without needing the Tap Forms application
- Migrate to a modern, free tool that works on Mac, iPhone, iPad, and Windows
- Ensure their data stays readable and usable for years to come
- Keep their photos, notes, and structured records together in one place

### Why Obsidian?

[Obsidian](https://obsidian.md) is a free, well-regarded note-taking application used by hundreds of thousands of people. It stores everything as plain text files on your own computer — not in a proprietary database or someone else's cloud. This means your data is always yours: you can read it, search it, back it up, and even open the files in any text editor.

Obsidian is built by a small, focused company (Obsidian Inc.) that has earned trust in the productivity community by committing to local-first data storage and long-term sustainability. Even if Obsidian the app were to disappear someday, your files would still be perfectly readable — they're just text and images in folders. That's the whole point.

Your Tap Forms records become neatly organized Obsidian notes with searchable fields, linked indexes, and embedded photos — ready to browse, edit, and build on.

---

## Step 1: Create your Tap Forms backup (.tfarc file)

Before you can convert your data, you need to export it from Tap Forms as a `.tfarc` archive. This is Tap Forms' own backup format and it includes all of your records, field definitions, and photo attachments.

### In Tap Forms 5 for Mac:

1. Open Tap Forms
2. Go to the menu bar and choose **File > Back Up Database...**
3. Choose a location to save the file (your Desktop or Documents folder is fine)
4. Tap Forms will create a file ending in `.tfarc` — this is your backup

### In Tap Forms on iPhone or iPad:

1. Open Tap Forms
2. Tap the **gear icon** (Settings)
3. Choose **Back Up / Restore**
4. Tap **Back Up Now**
5. Use the share sheet to save the `.tfarc` file to **Files**, or AirDrop it to your Mac

> **Tip:** The `.tfarc` file contains everything — all forms, all records, all photos. You only need one backup file to convert your entire database.

For more details, consult the [Tap Forms documentation](https://www.tapforms.com/help/) or search the Tap Forms help menu within the app.

---

## Step 2: Download the converter

Download the Python script to your Mac. The simplest way:

1. **Click this link to download:** [tfarc2obsidian.py](https://raw.githubusercontent.com/scottdunnflux/tfarc2obsidian/main/tfarc2obsidian.py)
2. Save it somewhere easy to find — your **Desktop** or **Downloads** folder works fine

> If the link opens as text in your browser instead of downloading, right-click (or Control-click) the link and choose **"Download Linked File"** or **"Save Link As..."**

---

## Step 3: Install Obsidian (if you haven't already)

Download Obsidian for free from the official site:

**https://obsidian.md**

Install it like any other Mac app — open the `.dmg` file and drag Obsidian to your Applications folder. You don't need to create an account or pay anything.

---

## Step 4: Run the converter

Open **Terminal** on your Mac. You can find it by pressing **Command + Space**, typing `Terminal`, and pressing Enter.

Then type the following command, replacing the path with the actual location of your `.tfarc` file:

```
python3 ~/Downloads/tfarc2obsidian.py ~/Desktop/"My Database 2026-05-25.tfarc"
```

> **Adjust the paths above** to match where you saved the script and your `.tfarc` file. If your filenames contain spaces, wrap them in quotes as shown.

The converter will show its progress as it works:

```
Loading archive...
Building schema...
  Found 7 forms, 96 fields, 695 records
Generating markdown...

Writing vault to: My Database 2026-05-25
  Writing 695 markdown files...
  Extracting 617 attachments...
  Attachments: 100/617 (108 MB extracted)
  ...
Done! Created 1320 files in My Database 2026-05-25
```

A new folder will appear next to your `.tfarc` file — this is your Obsidian vault.

### Optional flags

**Preview what will be created** without writing any files:

```
python3 ~/Downloads/tfarc2obsidian.py ~/Desktop/"My Database.tfarc" --dry-run
```

**Choose where to save the vault:**

```
python3 ~/Downloads/tfarc2obsidian.py ~/Desktop/"My Database.tfarc" -o ~/Documents/MyVault
```

---

## Step 5: Open your new vault in Obsidian

1. Open **Obsidian**
2. Click **"Open folder as vault"**
3. Navigate to the folder the converter created and select it
4. Your data is ready to explore!

You'll see a folder for each of your Tap Forms forms (Contacts, Home Inventory, etc.), with every record as its own note. Each folder has an **_Index** note that links to all its records, and the vault **README** links to every form.

---

## What gets converted

| Tap Forms | Obsidian |
|-----------|----------|
| Each form | A folder |
| Each record | A markdown note with searchable YAML fields |
| Text, phone, email, date, number fields | YAML frontmatter (structured, searchable) |
| Notes fields | Markdown text in the note body |
| Photos and images | Extracted to `_attachments/` folder, embedded in notes |
| Checkboxes | True/false values |
| Pick list values | Plain text |

---

## Requirements

- **macOS 12 (Monterey) or later** — any Mac from the last five years
- **Python 3** — already installed on your Mac if you have Xcode Command Line Tools. To check, open Terminal and type `python3 --version`. If you get "command not found," install the tools by running `xcode-select --install`
- No other software or downloads required — the converter has zero dependencies

---

## Questions & Troubleshooting

**"command not found: python3"**
Run `xcode-select --install` in Terminal and follow the prompts. This installs Python 3 along with other developer tools. It's free and provided by Apple.

**"Error: output directory already exists"**
The converter won't overwrite an existing vault. Either delete the old folder, rename it, or use `-o` to write to a different location.

**"Error: not a valid ZIP/tfarc file"**
Make sure you're pointing to the `.tfarc` file itself, not a folder or a different file type.

**My photos aren't showing in Obsidian**
Make sure the `_attachments` folder is inside the vault folder. Obsidian should find and display embedded images automatically. If images appear as broken links, try closing and reopening the vault.

**Can I edit my data after converting?**
Absolutely — that's the point! Your notes are plain text files. Edit them in Obsidian, add new notes, reorganize folders, or even open them in any text editor.
