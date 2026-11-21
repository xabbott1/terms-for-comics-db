# Terms for Comics DB

A simple Python/Tkinter scratch-pad app with six text boxes for copying and pasting comic-related terms.

## Requirements

- Python 3 with Tkinter (standard library)
- Linux desktop (works anywhere Tkinter runs)

## Run

```bash
python3 terms_for_comics_db.py
```

Or, if executable:

```bash
./terms_for_comics_db.py
```

## Features

- One window with a 2×3 grid of text boxes (multi-line, with scrollbars)
- A **Copy** button above each box to copy that box's full contents to the clipboard
- An **Always on top** checkbox to keep the window above other windows
- Uses standard window title-bar controls (minimize/close)

## Saving

- Each box is saved as a separate plain-text file: `1.txt` through `6.txt`
  - Order: top-left to top-right = 1–3, bottom-left to bottom-right = 4–6
- Autosaves every 3 minutes when there are unsaved changes, and performs a final save on close
- Writes are attempted atomically to reduce corruption risk

### Storage location fallback

When saving, the app tries these locations in order (creating folders as needed):

1. `~/.config/comicterms/`
2. `comicterms/` in the same folder as the program
3. `~/Desktop/comicterms/`
4. `comicterms/` in the system temp directory

If a save fails at the current location, it moves to the next location without showing an error dialog. If all locations fail (including temp), the program closes.

On startup, the app selects the first writable location (if any) and loads existing `1.txt`–`6.txt` from it. If no writable location is available, the app still opens and can be used as a non-saving scratch pad until a save succeeds somewhere.
