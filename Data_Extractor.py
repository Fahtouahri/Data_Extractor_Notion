import requests
import re
import pandas as pd
import os
from tqdm import tqdm

# Notion API authentication details (anonymized)
NOTION_TOKEN = os.getenv('NOTION_TOKEN')  # Retrieve the token from environment variables for security
DATABASE_ID = os.getenv('DATABASE_ID')    # Retrieve the database ID from environment variables
NOTION_VERSION = '2022-06-28'             # Version of the Notion API being used

# Set up headers for Notion API requests
headers = {
    'Authorization': f'Bearer {NOTION_TOKEN}',  # Authorization using the token
    'Content-Type': 'application/json',
    'Notion-Version': NOTION_VERSION
}

# Function to retrieve items from the Notion database using pagination
def get_database_items(database_id, start_cursor=None):
    url = f'https://api.notion.com/v1/databases/{database_id}/query'
    payload = {}
    if start_cursor:
        payload['start_cursor'] = start_cursor  # Pass the start cursor if it's provided for pagination
    response = requests.post(url, headers=headers, json=payload)
    if response.status_code != 200:
        print(f"Error during API request to Notion: {response.status_code}")
        print(response.json())
        return None
    return response.json()

# Function to get the blocks (content) of a Notion page by page ID
def get_page_blocks(page_id):
    url = f"https://api.notion.com/v1/blocks/{page_id}/children"
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        print(f"Error during API request to Notion: {response.status_code}")
        print(response.json())
        return None
    return response.json()

# Function to extract organization ID from the blocks of a Notion page
def extract_org_id_from_blocks(blocks):
    # Regular expression pattern to match UUID (organization ID format)
    org_id_pattern = r'\b[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12}\b'
    for block in blocks.get('results', []):
        block_type = block['type']
        block_data = block[block_type]
        if block_type in ['paragraph', 'heading_1', 'heading_2', 'heading_3', 'bulleted_list_item', 'numbered_list_item', 'to_do', 'toggle', 'callout', 'quote']:
            text = ''.join([text_part['plain_text'] for text_part in block_data.get('rich_text', [])])
            match = re.search(org_id_pattern, text)  # Search for the organization ID in the text
            if match:
                return match.group(0)  # Return the found ID
    return None  # Return None if no ID was found

# Function to extract relevant card information (link, title, org_id)
def extract_card_info(database_items, progress_bar):
    card_info_list = []
    for item in database_items.get('results', []):
        properties = item.get('properties', {})
        # Check if the "ORGA ID*" property exists and is not empty
        orga_id_property = properties.get('ORGA ID*', {})
        if orga_id_property and orga_id_property.get('rich_text'):
            continue  # Skip card if "ORGA ID*" is already filled

        # Retrieve the title of the card (property of type "title")
        title_property = next((prop for prop in properties.values() if prop['type'] == 'title'), None)
        if title_property:
            title = ''.join([text['plain_text'] for text in title_property['title']])
        else:
            title = "Title not found"

        # Build the link to the card using its ID
        page_id = item['id'].replace('-', '')  # The ID of the card without hyphens
        link = f"https://www.notion.so/{page_id}"

        # Extract the organization ID from the first page of blocks
        blocks = get_page_blocks(item['id'])
        org_id = extract_org_id_from_blocks(blocks) if blocks else None

        if org_id:
            card_info_list.append({
                'Link': link,
                'Card Title': title,
                'Org ID': org_id,
                'Source': 'Corpus'
            })

        # Update the progress bar
        progress_bar.update(1)

    return card_info_list

# Function to create a pandas DataFrame from the extracted card information
def create_dataframe(card_info_list):
    return pd.DataFrame(card_info_list)

# Main function to handle the full extraction process
def main():
    start_cursor = None
    all_card_info = []
    total_cards = 0

    # Estimate the total number of cards
    initial_response = get_database_items(DATABASE_ID)
    if initial_response is None:
        print("Error during initial request to Notion API.")
        return
    total_cards = initial_response.get('total', 0)

    # Initialize the progress bar
    progress_bar = tqdm(total=total_cards, desc="Processing cards", unit="card")

    while True:
        # Fetch the next batch of database items
        database_items = get_database_items(DATABASE_ID, start_cursor)
        if database_items is None:
            break
        card_info_list = extract_card_info(database_items, progress_bar)
        all_card_info.extend(card_info_list)
        # Check if there is a next page of results
        if not database_items.get('has_more'):
            break
        start_cursor = database_items.get('next_cursor')

    progress_bar.close()

    # If card info was found, save it to a CSV file
    if all_card_info:
        df = create_dataframe(all_card_info)
        # Path to the user's desktop
        desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
        csv_path = os.path.join(desktop_path, 'orga_ids.csv')
        df.to_csv(csv_path, index=False)
        print(f"Card information has been written to {csv_path}")
    else:
        print("No cards were found with an organization ID in the body.")

if __name__ == '__main__':
    main()
