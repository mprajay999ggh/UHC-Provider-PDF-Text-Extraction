import pandas as pd
from utils import process_all_files, save_text
from config import column_coords, file_page_config, specialty_threshold


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
