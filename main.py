import pdfplumber
import re
import pandas as pd

# Define column boundaries: (x0, top, x1, bottom)
column_coords = [
    (0, 80, 222, 677),     # Left column
    (222, 80, 404, 677),   # Middle column
    (404, 80, 612, 677)    # Right column
]


def save_text(str,file_name):
    with open(file_name, "w", encoding="utf-8") as f:
        f.write(str)
    
# Extract text from all three columns and specialty headers (by font size) in a single pass
all_text_blocks = []
specialty_lines = []
specialty_threshold = 12.25  # Adjust as needed based on your font size analysis

with pdfplumber.open("input/NY-EP-Provider-Directory-Upstate-West 1.pdf") as pdf:
    for page in pdf.pages:

        # Extract specialty headers by font size
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

        # Extract text from all three columns
        for (x0, top, x1, bottom) in column_coords:
            cropped = page.crop((x0, top, x1, bottom))
            column_text = cropped.extract_text()
            if column_text:
                all_text_blocks.append(column_text.strip())
        print(page)

# Combine all text blocks column-wise
combined_text = "\n\n".join(all_text_blocks)

lines = combined_text.split('\n')
merged_lines = []
buffer = ""

for line in lines:
    stripped = line.strip()
    if buffer:
        buffer += " " + stripped
    else:
        buffer = stripped
    
    if not stripped.endswith(','):
        merged_lines.append(buffer)
        buffer = ""

# In case last line ends with comma but there's nothing after it
if buffer:
    merged_lines.append(buffer)

# Final output
combined_text_final = "\n".join(merged_lines)
#print(combined_text_final)
save_text(combined_text_final, "combined_text.txt")
# --- Split into entries using gender marker ---
entries = []
entries_areas_of_expertise = []
current_entry = ""
flag = False

for line in combined_text_final.splitlines():
    line = line.strip()
    if not line:
        continue
    # If line contains (M) or (F) as a standalone gender indicator
    if re.search(r'\([MF]\)', line):
        flag = True
        if current_entry.strip():
            entries.append(current_entry.strip())
        current_entry = line
    else:
        #if flag == True:
        current_entry += ' ' + line

#print(entries)




# --- Assign specialties to entries (specialty applies to next entry only, robust) ---
current_specialty = None
for i in range(len(entries)):
    # Apply current specialty to this entry
    if current_specialty:
        entries[i] += f"\nAreas of Expertise: {current_specialty.split('/')[0].strip()}"
    # Find specialty for the next entry
    for specialty in specialty_lines:
        if specialty != current_specialty and specialty in entries[i]:
            current_specialty = specialty
            entries[i] = entries[i].replace(specialty, "")
            break

        



print("Specialty Lines:", specialty_lines)

# Save entries to a text file
save_text("\n\n".join(entries), "output/entries.txt")



# --- ADA Feature Legend ---
ADA_FEATURE_CODES = {
    "W": "Wheelchair",
    "PT": "Public Transportation nearby",
    "B": "Board Certified",
    "P": "Parking",
    "EB": "Exterior Building",
    "IB": "Interior Building",
    "R": "Restroom",
    "E": "Exam Room",
    "T": "Exam Table/Scale/Chairs",
    "G": "Gurneys & Stretchers",
    "PL": "Portable Lifts",
    "RE": "Radiologic Equipment",
    "S": "Signage & Documents"
}

# --- Parse each entry into structured fields ---
def parse_entry(text,areas_of_expertise=None):

    if not re.search(r'\([MF]\)', text):
        return None
    
    result = {
        'Provider_Category': 'PCP',
        'Provider_Specialty': 'Primary Care',  # Default assumption
        'Provider_FIRST_Name': None,
        'PROVIDER_MIDDLE_NAME': None,
        'PROVIDER_LAST_Name': None,
        'Degree': None,
        'Gender': None,
        'Organization': None,
        'Group_Name': None,
        'Provider_ID': None,
        'NPI': None,
        'License_Number': None,
        'Address_Line': None,
        'City': None,
        'State': 'NY',
        'County': None,
        'ZIP': None,
        'Phone': None,
        'Languages': [],
        'ADA_Features': [],
        'Days_Hours': None,
        'Accepting_New_Patients': False,
        'Hospital_Affiliations': None,
        'Age_Group': None,
        'Areas_of_Expertise': None,
        'Web_Address': None
    }

    # Name, Degree, Gender
    name_match = re.match(r"([^,]+),\s+([^,]+)(?:\s+([A-Z])\.)?,\s+(MD|DO|MS|FNP|NP|DNP|MSN|NON|M D|MA|AUD),\s+\((M|F)\)", text)
    if name_match:
        result['PROVIDER_LAST_Name'] = name_match.group(1).strip()
        result['Provider_FIRST_Name'] = name_match.group(2).strip()
        result['PROVIDER_MIDDLE_NAME'] = name_match.group(3) if name_match.group(3) else None
        result['Degree'] = name_match.group(4)
        result['Gender'] = name_match.group(5)

    # Group Name
    group_match = re.search(r"Group Name:\s*(.*?)\s+Provider ID:", text)
    if group_match:
        result['Group_Name'] = group_match.group(1).strip()

    # Provider ID
    pid_match = re.search(r"Provider ID:\s*(\d+)", text)
    if pid_match:
        result['Provider_ID'] = pid_match.group(1)

    # NPI
    npi_match = re.search(r"NPI:\s*(\d+)", text)
    if npi_match:
        result['NPI'] = npi_match.group(1)

    # Address
    address_match = re.search(r"NPI:\s*\d+\s+(.*?)\s+\(?\d{3}\)?[-\s]\d{3}[-]\d{4}", text)
    if address_match:
        full_address = address_match.group(1)
        address_parts = full_address.rsplit(" ", 2)
        if len(address_parts) == 3:
            result['Address_Line'] = address_parts[0]
            result['City'] = address_parts[1].rstrip(",")
            result['ZIP'] = address_parts[2]

    # Phone
    phone_match = re.search(r"\(\d{3}\)\s*\d{3}-\d{4}", text)
    if phone_match:
        result['Phone'] = phone_match.group(0)

    # Languages
    lang_match = re.search(r"Languages Spoken:.*?Provider:\s*([A-Za-z,\s]+)", text)
    if lang_match:
        result['Languages'] = [lang.strip() for lang in lang_match.group(1).split(",")]

    

    # ADA Features
    ada_matches = re.findall(r"\b(W|PT|B|P|EB|IB|R|E|T|G|PL|RE|S)\b", text)
    result['ADA_Features'] = list(set(ADA_FEATURE_CODES.get(code, code) for code in ada_matches))

    # Days and Hours

    hours_match = re.search(
    r"((?:Mo|Tu|We|Th|Fr|Sa|Su)[,\-\s].*?M\b.*?)(?:Accepting New Patients|Hospital Affiliations|Languages|Cultural|Web address|Areas of Expertise|Accepting Existing Patients Only|Does Not Accept New Patients|$)",
    text
)


    if hours_match:
        result['Days_Hours'] = hours_match.group(1).strip()
    else:

        result['Days_Hours'] = "Mo-Fr - 8:00 AM - 5:00 PM"

    # Accepting New Patients
    if "Accepting New Patients" in text:
        result['Accepting_New_Patients'] = True

    # Age Group
    age_match = re.search(r"Ages:\s*(\d+-\d+)", text)
    if age_match:
        result['Age_Group'] = age_match.group(1)

    # Hospital Affiliations
    hosp_match = re.search(r"Hospital Affiliations:\s*(.*?)\s*(Languages|Cultural|Areas of Expertise|Areas|Web address|Accepting|$)", text)
    if hosp_match:
        result['Hospital_Affiliations'] = hosp_match.group(1).strip()

    # Areas of Expertise
    expertise_match = re.search(r"Areas of Expertise:\s*(.*)", text)
    if expertise_match:
        # Only take up to the next line break or separator if present
        value = expertise_match.group(1).strip()
        # Remove trailing text after a separator if present
        value = value.split('\n')[0].split('|')[0].strip()
        result['Areas_of_Expertise'] = value if value else None

    # Web Address
    web_match = re.search(r"Web address:\s*(\S+)", text)
    if web_match:
        result['Web_Address'] = web_match.group(1).strip()

    return result



# --- Parse all entries, skipping None results ---
parsed_data = [r for r in (parse_entry(e) for e in entries) if r is not None]

# --- Convert to DataFrame ---
df = pd.DataFrame(parsed_data)

# Output to Excel
df.to_csv("output/test.csv", index=False)

# Optional: Print first few rows
#print(df.head())
