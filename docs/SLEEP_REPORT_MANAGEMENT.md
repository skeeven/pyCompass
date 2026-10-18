# Sleep report management (local development)

Compass Health → Sleep report imports accepts **ResMed CPAP** and **Sleep Cycle** PDFs.

- ResMed: OCR identifies dated aggregate report sections for user confirmation.
- Sleep Cycle: first attempts embedded text; if unavailable or unsupported,
  falls back to bounded OCR. Recognized text is displayed for review and
  the user enters the correct period and confirms each metric.
- For Sleep Cycle, the importer can suggest an explicitly labeled
  "average sleep" value in hours when recognized. The suggestion is not
  automatically saved. Other values can be manually entered and confirmed.
- OCR requires `pytesseract`, PyMuPDF, Pillow and a locally installed
  Tesseract executable (`brew install tesseract` on Mac).
- The original PDF and OCR text are not persisted by Compass.
- Reports are considered duplicates when the **same account, source,
  start date and end date** already exist. Overlapping 30-, 90-, and
  365-day period reports remain valid separate records.
- A duplicate is refused, even if its metrics differ. ResMed multi-period
  imports save new periods and skip previously saved periods.
- Health → Health history lists saved periods. Expand a period, check
  the permanent-delete confirmation, then click **Delete report period**.
  This removes the period and all attached metrics for the signed-in
  account. The period can then be imported again.
- Existing duplicate records imported before this change are **not**
  deleted automatically; inspect and delete unwanted records manually.
- Only checked, user-confirmed summaries are saved. No clinical
  conclusions are drawn from OCR or imported measurements.

## Local verification

```bash
git pull origin feature/compass-health
python -m pytest -q
python -m streamlit run app.py
```

For OCR manual verification, import a real Sleep Cycle PDF containing
scanned pages, verify the recognized text, edit any measurements, and
confirm the reporting period. Test repeated imports, account isolation
and deleting an incorrect period.

**Limitations:** Text recognition and date/metric extraction depend
on the Sleep Cycle export layout and scan quality. This project has
not yet been verified with the user's actual Sleep Cycle PDF.
