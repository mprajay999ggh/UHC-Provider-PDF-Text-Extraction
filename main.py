import pandas as pd
from utils import process_all_files, save_text

# Define column boundaries: (x0, top, x1, bottom)
column_coords = [
    (0, 80, 222, 677),     # Left column
    (222, 80, 404, 677),   # Middle column
    (404, 80, 612, 677)    # Right column
]

# Configuration - specify files with their categories, pages, and provider types
file_page_config = [
    {
        "file": "input/NY-EP-Provider-Directory-Bronx 1.pdf",
        "categories": [
            {"pages": [1], "provider_category": "PCP"},
            {"pages": [2], "provider_category": "Specialist"},
            {"pages": [3], "provider_category": "Mental Health"}
        ]
    },
    {
        "file": "input/NY-EP-Provider-Directory-Bronx 1-1.pdf",
        "categories": [
            {"pages": [1], "provider_category": "PCP"},
            {"pages": [2], "provider_category": "Specialist"},
            {"pages": [3], "provider_category": "Mental Health"}
        ]
    },
    {
        "file": "input/NY-EP-Provider-Directory-Upstate-West 1.pdf",
        "categories": [
            {"pages": [1], "provider_category": "PCP"},
            {"pages": [2], "provider_category": "Specialist"},
            {"pages": [3], "provider_category": "Mental Health"}
        ]
    },
    {
        "file": "input/test.pdf",
        "categories": [
            {"pages": [1], "provider_category": "PCP"},
            {"pages": [2], "provider_category": "Specialist"},
            {"pages": [3], "provider_category": "Mental Health"}
        ]
    }
]
specialty_threshold = 12.25  # Adjust as needed based on your font size analysis


def main():
    """Main function to orchestrate the PDF processing workflow."""
    print("Starting PDF processing...")
    
    # Process all files
    all_entries, all_specialty_lines, all_parsed_data = process_all_files(
        file_page_config, specialty_threshold, column_coords
    )
    
    # Create a combined CSV with all data as well
    if all_parsed_data:
        df_combined = pd.DataFrame(all_parsed_data)
        df_combined.to_csv("output/combined_all.csv", index=False)
        print(f"Saved combined CSV with {len(all_parsed_data)} total entries to output/combined_all.csv")

if __name__ == "__main__":
    main()
