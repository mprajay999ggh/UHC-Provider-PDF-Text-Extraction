import pdfplumber
import re
import pandas as pd

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


def save_text(text, file_name):
    """Save text content to a file."""
    with open(file_name, "w", encoding="utf-8") as f:
        f.write(text)


def extract_specialty_headers(page, specialty_threshold):
    """Extract specialty headers by font size from a PDF page."""
    words = page.extract_words(extra_attrs=["size"])
    specialty_lines = []
    current_line = []
    
    for word in words:
        if word.get("size", 0) >= specialty_threshold:
            current_line.append(word["text"])
        elif current_line:
            specialty_lines.append(" ".join(current_line).strip())
            current_line = []
    
    if current_line:
        specialty_lines.append(" ".join(current_line).strip())
    
    return specialty_lines


def extract_column_text(page, column_coords):
    """Extract text from all specified columns on a PDF page."""
    text_blocks = []
    
    for (x0, top, x1, bottom) in column_coords:
        cropped = page.crop((x0, top, x1, bottom))
        column_text = cropped.extract_text()
        if column_text:
            text_blocks.append(column_text.strip())
    
    return text_blocks


def merge_comma_separated_lines(text):
    """Merge lines that end with commas with the following line."""
    lines = text.split('\n')
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

    return "\n".join(merged_lines)


def split_into_entries(text):
    """Split text into individual provider entries using gender markers."""
    entries = []
    current_entry = ""

    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        
        # If line contains (M) or (F) as a standalone gender indicator
        if re.search(r'\([MF]\)', line):
            if current_entry.strip():
                entries.append(current_entry.strip())
            current_entry = line
        else:
            current_entry += ' ' + line

    # Add the last entry
    if current_entry.strip():
        entries.append(current_entry.strip())

    return entries


def assign_specialties_to_entries(entries, specialty_lines):
    """Assign specialty information to provider entries."""
    current_specialty = None
    
    for i in range(len(entries)):
        # Apply current specialty to this entry
        if current_specialty:
            entries[i] += f"\nProvider Specialty: {current_specialty.split('/')[0].strip()}"
        
        # Find specialty for the next entry
        for specialty in specialty_lines:
            if specialty != current_specialty and specialty in entries[i]:
                current_specialty = specialty
                entries[i] = entries[i].replace(specialty, "")
                break

    return entries


def parse_entry(text, provider_category="PCP"):
    """Parse a single provider entry into structured fields."""
    if not re.search(r'\([MF]\)', text):
        return None
    
    result = {
        'Provider_Category': provider_category,
        'Provider_Specialty': None,  
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

    # Extract Provider Category from the text (similar to how we extract specialty)
    provider_category_match = re.search(r"Provider Category:\s*(.*)", text)
    if provider_category_match:
        value = provider_category_match.group(1).strip()
        value = value.split('\n')[0].split('|')[0].strip()
        result['Provider_Category'] = value if value else provider_category

    # Name, Degree, Gender
    name_match = re.match(r"([^,]+),\s+([^,]+)(?:\s+([A-Z])\.)?,\s+([A-Za-z\. ]{1,4}),\s+\((M|F)\)", text)
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
    hosp_match = re.search(r"Hospital Affiliations:\s*(.*?)\s*(Languages|Cultural|Areas of Expertise|Areas|Web address|Accepting|Provider|$)", text)
    if hosp_match:
        result['Hospital_Affiliations'] = hosp_match.group(1).strip()

    # Provider Specialty
    Provider_Specialty_match = re.search(r"Provider Specialty:\s*(.*)", text)
    if Provider_Specialty_match:
        # Only take up to the next line break or separator if present
        value = Provider_Specialty_match.group(1).strip()
        # Remove trailing text after a separator if present
        value = value.split('\n')[0].split('|')[0].strip()
        result['Provider_Specialty'] = value if value else None

    # Web Address
    web_match = re.search(r"Web address:\s*(\S+)", text)
    if web_match:
        result['Web_Address'] = web_match.group(1).strip()

    # Areas of Expertise
    expertise_match = re.search(r"Areas of Expertise:\s*(.*)", text)
    if expertise_match:
        # Only take up to the next line break or separator if present
        value = expertise_match.group(1).strip()
        # Remove trailing text after a separator if present
        value = value.split('\n')[0].split('|')[0].strip()
        # Extract only substrings matching the pattern: one letter followed by two digits, possibly surrounded by commas
        matches = re.findall(r',?\s*([A-Za-z]\d{2})\s*,?', value)
        result['Areas_of_Expertise'] = ', '.join(matches) if matches else None

    return result


def process_single_category(input_file, page_numbers, provider_category, specialty_threshold, column_coords):
    """Process a single category (set of pages) from a PDF file."""
    print(f"Processing {provider_category} - Pages {page_numbers}")
    
    all_text_blocks = []
    specialty_lines = []
    
    with pdfplumber.open(input_file) as pdf:
        for page_num in page_numbers:
            if page_num > len(pdf.pages):
                print(f"Page {page_num} not found in {input_file}")
                continue
                
            page = pdf.pages[page_num - 1]
            print(f"Processing page {page_num}")
            
            # Extract specialty headers
            page_specialty_lines = extract_specialty_headers(page, specialty_threshold)
            specialty_lines.extend(page_specialty_lines)
            
            # Extract text from columns
            page_text_blocks = extract_column_text(page, column_coords)
            all_text_blocks.extend(page_text_blocks)

    # Combine and process text
    combined_text = "\n\n".join(all_text_blocks)
    combined_text_final = merge_comma_separated_lines(combined_text)
    
    # Split into entries and assign specialties
    entries = split_into_entries(combined_text_final)
    entries = assign_specialties_to_entries(entries, specialty_lines)
    
    # Append provider category to each entry
    entries_with_category = []
    for entry in entries:
        entry_with_category = entry + f"\nProvider Category: {provider_category}"
        entries_with_category.append(entry_with_category)
    
    # Parse entries for this category
    parsed_data = []
    for entry in entries_with_category:
        parsed_entry = parse_entry(entry)
        if parsed_entry is not None:
            parsed_data.append(parsed_entry)
    
    # Create output filename for this file-category combination
    file_name = input_file.split('/')[-1].replace('.pdf', '').replace(' ', '_').replace('-', '_')
    category_name = provider_category.replace(' ', '_').replace('-', '_')
    output_filename = f"output/{file_name}_{category_name}.csv"
    
    # Save category-specific CSV
    if parsed_data:
        df = pd.DataFrame(parsed_data)
        df.to_csv(output_filename, index=False)
        print(f"Saved {len(parsed_data)} entries to {output_filename}")
    
    return entries_with_category, specialty_lines, parsed_data


def process_single_file(input_file, categories, specialty_threshold, column_coords):
    """Process a single PDF file with multiple categories."""
    print(f"Processing file: {input_file}")
    
    all_entries = []
    all_specialty_lines = []
    all_parsed_data = []
    
    for category in categories:
        page_numbers = category["pages"]
        provider_category = category["provider_category"]
        
        entries, specialty_lines, parsed_data = process_single_category(
            input_file, page_numbers, provider_category, specialty_threshold, column_coords
        )
        
        all_entries.extend(entries)
        all_specialty_lines.extend(specialty_lines)
        all_parsed_data.extend(parsed_data)
    
    # Save combined text for this file
    file_name = input_file.split('/')[-1].replace('.pdf', '')
    all_combined_text = "\n\n".join(all_entries)
    save_text(all_combined_text, f"combined_text_{file_name}.txt")
    
    return all_entries, all_specialty_lines, all_parsed_data


def process_all_files(file_page_config, specialty_threshold, column_coords):
    """Process all configured files and return combined results."""
    all_entries = []
    all_specialty_lines = []
    all_parsed_data = []

    for config in file_page_config:
        input_file = config["file"]
        categories = config["categories"]
        
        entries, specialty_lines, parsed_data = process_single_file(
            input_file, categories, specialty_threshold, column_coords
        )
        
        all_entries.extend(entries)
        all_specialty_lines.extend(specialty_lines)
        all_parsed_data.extend(parsed_data)

    return all_entries, all_specialty_lines, all_parsed_data
