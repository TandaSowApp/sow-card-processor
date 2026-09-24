from datetime import datetime, timedelta
import fitz  # PyMuPDF
import streamlit as st


# ==========================================
# 1. YOUR PROCESSING LOGIC
# ==========================================
def process_sow_cards_bytes(pdf_bytes):
  doc = fitz.open(stream=pdf_bytes, filetype="pdf")
  updated_count = 0

  for page_num in range(len(doc)):
    page = doc[page_num]
    page_rect = page.rect
    mid_y = page_rect.height / 2

    top_zone = fitz.Rect(0, 0, page_rect.width, mid_y)
    bottom_zone = fitz.Rect(0, mid_y, page_rect.width, page_rect.height)

    # --- PROCESS TOP CARD ---
    top_text = page.get_text("text", clip=top_zone)
    if "ROYAL CRESCENT" in top_text or "Parity" in top_text:
      (
          should_dx,
          should_induce,
          stillborn_rects,
          breed_rects,
          max_parity,
          induce_date_str,
      ) = evaluate_sow_card(page, top_zone, top_text)

      if max_parity >= 3 and (should_dx or stillborn_rects or breed_rects):
        if should_dx:
          page.insert_text(
              fitz.Point(top_zone.x0 + 10, top_zone.y1 - 85),
              "DX",
              fontsize=20,
              color=(1, 0, 0),
              rotate=270,
          )

        if should_induce and induce_date_str:
          page.insert_text(
              fitz.Point(top_zone.x1 - 110, top_zone.y0 + 90),
              induce_date_str,
              fontsize=14,
              color=(1, 0, 0),
          )

        for rect in stillborn_rects:
          highlight = page.add_highlight_annot(rect)
          highlight.set_colors(stroke=(1, 1, 0))  # Yellow
          highlight.update()

        for rect, b_type in breed_rects:
          highlight = page.add_highlight_annot(rect)
          if b_type == "kanto":
            highlight.set_colors(stroke=(0, 0, 1))  # Blue
          elif b_type == "landrace":
            highlight.set_colors(stroke=(0, 1, 0))  # Green
          highlight.update()

        updated_count += 1

    # --- PROCESS BOTTOM CARD ---
    bottom_text = page.get_text("text", clip=bottom_zone)
    if "ROYAL CRESCENT" in bottom_text or "Parity" in bottom_text:
      (
          should_dx,
          should_induce,
          stillborn_rects,
          breed_rects,
          max_parity,
          induce_date_str,
      ) = evaluate_sow_card(page, bottom_zone, bottom_text)

      if max_parity >= 3 and (should_dx or stillborn_rects or breed_rects):
        if should_dx:
          page.insert_text(
              fitz.Point(bottom_zone.x0 + 10, bottom_zone.y1 - 115),
              "DX",
              fontsize=20,
              color=(1, 0, 0),
              rotate=270,
          )

        if should_induce and induce_date_str:
          page.insert_text(
              fitz.Point(bottom_zone.x1 - 110, bottom_zone.y0 + 45),
              induce_date_str,
              fontsize=14,
              color=(1, 0, 0),
          )

        for rect in stillborn_rects:
          highlight = page.add_highlight_annot(rect)
          highlight.set_colors(stroke=(1, 1, 0))  # Yellow
          highlight.update()

        for rect, b_type in breed_rects:
          highlight = page.add_highlight_annot(rect)
          if b_type == "kanto":
            highlight.set_colors(stroke=(0, 0, 1))  # Blue
          elif b_type == "landrace":
            highlight.set_colors(stroke=(0, 1, 0))  # Green
          highlight.update()

        updated_count += 1

  output_pdf_bytes = doc.tobytes()
  doc.close()
  return output_pdf_bytes, updated_count


def evaluate_sow_card(page, zone, full_text):
  words = page.get_text("words", clip=zone)

  max_parity = 0
  stillborn_records = []
  parity_headers = []
  flag_tokens = []
  service_flag_tokens = []
  average_x = float("inf")

  for i, w in enumerate(words):
    text = w[4].strip()

    if text == "Average":
      average_x = w[0]

    if text == "Stillborn":
      row_y = w[1]
      for ow in words:
        if (
            ow[1] >= row_y - 4
            and ow[1] <= row_y + 5
            and ow[0] > w[2]
            and ow[4].strip().replace(".", "").isdigit()
        ):
          val_str = ow[4].strip()
          try:
            val = float(val_str)
            x_center = (ow[0] + ow[2]) / 2
            stillborn_records.append((x_center, val, ow))
          except ValueError:
            pass

    if "Parity" in text:
      row_y = w[1]
      for ow in words:
        if (
            ow[1] >= row_y - 4
            and ow[1] <= row_y + 6
            and ow[0] > w[2]
            and ow[4].strip().isdigit()
        ):
          p_val = int(ow[4].strip())
          if p_val > max_parity:
            max_parity = p_val
          x_center = (ow[0] + ow[2]) / 2
          parity_headers.append((p_val, x_center))

    if text == "Service":
      if i + 1 < len(words) and "Flag" in words[i + 1][4]:
        flag_row_y = w[1]
        for ow in words:
          if (
              ow[1] >= flag_row_y - 3
              and ow[1] <= flag_row_y + 5
              and ow[0] > w[2]
          ):
            x_center = (ow[0] + ow[2]) / 2
            service_flag_tokens.append((x_center, ow))

    if text == "Service" or text == "Farrow":
      if i + 1 < len(words) and "Flag" in words[i + 1][4]:
        flag_row_y = w[1]
        for ow in words:
          if (
              ow[1] >= flag_row_y - 3
              and ow[1] <= flag_row_y + 5
              and ow[0] > w[2]
          ):
            x_center = (ow[0] + ow[2]) / 2
            flag_tokens.append((x_center, ow[4].strip().lower()))

  if max_parity == 0:
    max_parity = 3

  parity_headers.sort(key=lambda x: x[1])
  stillborn_records.sort(key=lambda x: x[0])

  valid_stillborns = []
  for sx, val, ow in stillborn_records:
    if sx >= average_x - 10:
      continue
    valid_stillborns.append((sx, val, ow))

  stillborn_rects = []
  has_unresolved_high_stillborns = False
  has_latest_high_stillborn = False

  for idx, (sx, val, ow) in enumerate(valid_stillborns):
    p_num = max_parity
    if idx < len(parity_headers):
      p_num = parity_headers[idx][0]

    is_high = False
    if val >= 3.0:
      is_high = True
      r = fitz.Rect(ow[0] - 2, ow[1] - 2, ow[2] + 2, ow[3] + 2)
      stillborn_rects.append(r)
      if p_num == max_parity:
        has_latest_high_stillborn = True
    elif sx > 450 and val >= 2.0:
      is_high = True
      r = fitz.Rect(ow[0] - 2, ow[1] - 2, ow[2] + 2, ow[3] + 2)
      stillborn_rects.append(r)

    if is_high:
      subsequent_vals = [s[1] for s in valid_stillborns if s[0] > sx]
      if not subsequent_vals or any(v >= 2.0 for v in subsequent_vals):
        has_unresolved_high_stillborns = True

  latest_parity_flags = ""
  latest_service_flags = ""
  breed_rects = []

  if parity_headers:
    idx = -1
    for h_idx, h in enumerate(parity_headers):
      if h[0] == max_parity:
        idx = h_idx
        break

    if idx != -1:
      target_header_x = parity_headers[idx][1]
      left_bound = (
          (parity_headers[idx - 1][1] + target_header_x) / 2
          if idx > 0
          else target_header_x - 30
      )
      right_bound = (
          (target_header_x + parity_headers[idx + 1][1]) / 2
          if idx < len(parity_headers) - 1
          else target_header_x + 50
      )

      for fx, ftext in flag_tokens:
        if left_bound <= fx < right_bound:
          latest_parity_flags += f" {ftext}"

      for fx, ow in service_flag_tokens:
        if left_bound <= fx < right_bound:
          val_str = ow[4].strip().lower()
          latest_service_flags += f" {val_str}"
          if "kanto" in val_str:
            r = fitz.Rect(ow[0] - 2, ow[1] - 2, ow[2] + 2, ow[3] + 2)
            breed_rects.append((r, "kanto"))
          elif "landrace" in val_str:
            r = fitz.Rect(ow[0] - 2, ow[1] - 2, ow[2] + 2, ow[3] + 2)
            breed_rects.append((r, "landrace"))

  has_recent_combined_flag = (
      "i" in latest_parity_flags and "dx" in latest_parity_flags
  )
  has_early_service_flag = "early" in latest_service_flags

  should_induce = max_parity >= 4 and (
      has_recent_combined_flag
      or has_unresolved_high_stillborns
      or has_latest_high_stillborn
  )
  should_dx = max_parity >= 3 and (
      has_recent_combined_flag
      or has_unresolved_high_stillborns
      or has_latest_high_stillborn
  )

  induce_date_str = "Sep. 29"
  try:
    due_date = None
    day115 = None

    if "dueday:" in full_text:
      parts = full_text.split("dueday:")
      date_part = parts[1].strip().split()[0].replace(";", "")
      due_date = datetime.strptime(date_part, "%m/%d/%y")

    if "115day:" in full_text:
      parts = full_text.split("115day:")
      date_part = parts[1].strip().split()[0].replace(";", "")
      day115 = datetime.strptime(date_part, "%m/%d/%y")

    if due_date and day115:
      diff_days = (due_date - day115).days

      if diff_days == -2:
        target_date = day115 - timedelta(hours=60)
      elif diff_days in [-1, 0, 1]:
        target_date = day115 - timedelta(days=2)
      elif diff_days in [2, 3]:
        target_date = day115 - timedelta(days=1)
      else:
        target_date = day115

      if has_early_service_flag:
        target_date -= timedelta(days=1)

      month_str = target_date.strftime("%b")
      day_str = target_date.strftime("%d").lstrip("0")
      induce_date_str = f"{month_str}. {day_str}"
  except Exception:
    pass

  return (
      should_dx,
      should_induce,
      stillborn_rects,
      breed_rects,
      max_parity,
      induce_date_str,
  )


# ==========================================
# 2. STREAMLIT USER INTERFACE
# ==========================================
st.set_page_config(
    page_title="Sow Card Batch Processor", page_icon="📋", layout="centered"
)

st.title("📋 Sow Card Batch Processor")
st.markdown(
    "Upload your raw sow history record PDF. The app will evaluate parities,"
    " flag health metrics, and output a ready-to-print file."
)

uploaded_file = st.file_uploader(
    "Choose a sow card PDF file", type=["pdf"], key="sow_upload"
)

if uploaded_file is not None:
  st.success("File uploaded successfully!")

  file_details = {
      "FileName": uploaded_file.name,
      "FileSize": f"{uploaded_file.size / 1024:.2f} KB",
  }
  st.json(file_details)

  if st.button("Process Cards"):
    with st.spinner("Processing sow cards and applying rules..."):
      # Read file bytes directly from uploaded object
      pdf_bytes = uploaded_file.read()

      # Run processing function
      processed_bytes, count = process_sow_cards_bytes(pdf_bytes)

      st.success(
          f"Processing complete! Flagged {count} qualifying high-risk sows."
      )

      # Provide download link for the marked PDF
      st.download_button(
          label="📥 Download Processed PDF",
          data=processed_bytes,
          file_name=f"marked_{uploaded_file.name}",
          mime="application/pdf",
      )