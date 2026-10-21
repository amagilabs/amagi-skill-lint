---
name: pdf-forms
description: Fill, inspect and flatten fillable PDF forms (W-9, vendor onboarding, permit applications). Use when the user wants to fill a PDF form, list its fields, or check which fields are still empty.
allowed-tools: Bash(python *) Read
---

# PDF forms

1. List the fields: `python scripts/fill.py fields form.pdf`
2. Write the values to a YAML file. Field names and types are in [the field guide](reference/fields.md).
3. Fill: `python scripts/fill.py fill form.pdf values.yaml -o filled.pdf`

Checkboxes take `true`/`false`. Radio groups take the export value shown by `fields`.
