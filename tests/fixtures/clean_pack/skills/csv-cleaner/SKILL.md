---
name: csv-cleaner
description: Cleans messy CSV exports by trimming whitespace, fixing dates to ISO 8601 and dropping duplicate rows. Use when the user hands over a CSV that will not import cleanly into a spreadsheet or database.
---

# CSV cleaner

Run `python scripts/clean.py input.csv -o clean.csv`, then show the user the row counts before and after.
