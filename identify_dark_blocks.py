import pdfplumber
import re
import pandas as pd

# --- Extract specialty headers (by font size) from the PDF ---
specialty_lines = []
specialty_threshold = 12.25  # Adjust as needed based on your font size analysis
with pdfplumber.open("input/NY-EP-Provider-Directory-Bronx 1.pdf") as pdf:
    for page in pdf.pages:
        words = page.extract_words(extra_attrs=["size"])
        current_line = []
        for word in words:
            if word.get("size", 0) >= specialty_threshold:
                current_line.append(word["text"])
            elif current_line:
                specialty_lines.append(" ".join(current_line).strip())
                current_line = []
        if current_line:
            specialty_lines.append(" ".join(current_line).strip())


filtered_specialty_lines = []
for line in specialty_lines:
    if '/' in line:
        filtered_specialty_lines.append(line.split('/', 1)[0].strip())
    else:
        filtered_specialty_lines.append(line.strip())
print(filtered_specialty_lines)