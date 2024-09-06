# Notion Data Extractor

## Introduction
This Python script is designed to interact with a Notion database and extract specific information embedded within the content of pages (referred to as "cards"). It automates the process of finding and updating missing data fields in Notion cards and saves the results in a CSV file for easy tracking.

## Features
- **Information Retrieval**: Scans the content of cards in a Notion database to find specific information, such as organization IDs, embedded within the text.
- **Data Update**: Automatically updates the "ORGA ID*" field in Notion cards that are missing this information.
- **CSV Export**: Saves details about the processed cards, including their titles, links, and the extracted information, into a CSV file.
- **Progress Tracking**: Displays the real-time progress of card processing with a progress bar.
- **Prevents Duplicate Processing**: Skips already processed cards by checking for the presence of existing "ORGA ID*" information.

## Requirements
- Python 3.6 or higher
- Python libraries:
  - `requests`
  - `re`
  - `pandas`
  - `os`
  - `tqdm`

