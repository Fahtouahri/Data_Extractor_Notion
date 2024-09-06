import requests
import re
import pandas as pd
import os
from tqdm import tqdm

# Use environment variables to store sensitive information
NOTION_TOKEN = os.getenv('NOTION_TOKEN')  # Retrieve Notion token from environment variables
DATABASE_ID = os.getenv('DATABASE_ID')    # Retrieve Notion database ID from environment variables
NOTION_VERSION = '2022-06-28'             # Notion API version

# Set up the headers for the Notion API request
headers = {
    'Authorization': f'Bearer {NOTION_TOKEN}',  # Authorization using the Notion token
    'Content-Type': 'application/json',
    'Notion-Version': NOTION_VERSION
}

# Function to get database items from the Notion database
def get_database_items(database_id, start_cursor=None):
    url = f'https://api.notion.com/v1/databases/{database_id}/query'
    payload = {}
    if start_cursor:
        payload['start_cursor'] = start_cursor  # Pagination support with start_cursor
    response = requests.post(url, headers=headers, json=payload)
    if response.status_code != 200:
        print(f"Error during API request to Notion: {response.status_code}")
        print(response.json())
        return None
    return response.json()

# Function to get blocks (content) of a Notion page
def get_page_blocks(page_id):
    url = f"https://api.notion.com/v1/blocks/{page_id}/children"
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        print(f"Error during API request to Notion: {response.status_code}")
        print(response.json())
        return None
    return response.json()

# Function to extract organization ID from page blocks using regex
def extract_org_id_from_blocks(blocks):
    org_id_pattern = r'\b[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12}\b'
    for block in blocks.get('results', []):
        block_type = block['type']
        block_data = block[block_type]
        if block_type in ['paragraph', 'heading_1', 'heading_2', 'heading_3', 'bulleted_list_item', 'numbered_list_item', 'to_do', 'toggle', 'callout', 'quote']:
            text = ''.join([text_part['plain_text'] for text_part in block_data.get('rich_text', [])])
            matches = re.findall(org_id_pattern, text)  # Extract all matching org IDs
            if matches:
                return matches[0]  # Return the first found ID
    return None  # Return None if no ID is found

# Function to update the card with the extracted organization ID
def update_card_property(page_id, orga_id):
    url = f'https://api.notion.com/v1/pages/{page_id}'
    payload = {
        "properties": {
            "ORGA ID*": {
                "rich_text": [
                    {
                        "text": {
                            "content": orga_id
                        }
                    }
                ]
            }
        }
    }
    response = requests.patch(url, headers=headers, json=payload)
    if response.status_code != 200:
        print(f"Error during card update: {response.status_code}")
        print(response.json())
        return False
    return True

# Function to verify if the organization ID has been correctly updated on the card
def verify_card_property(page_id, expected_orga_id):
    url = f'https://api.notion.com/v1/pages/{page_id}'
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        print(f"Error during card verification: {response.status_code}")
        print(response.json())
        return False
    properties = response.json().get('properties', {})
    orga_id_property = properties.get('ORGA ID*', {})
    if orga_id_property and orga_id_property.get('rich_text'):
        orga_id_text = ''.join([text['plain_text'] for text in orga_id_property['rich_text']])
        if orga_id_text == expected_orga_id:
            return True
    return False

# Function to extract card information, handle processing, and avoid duplicates
def extract_card_info(database_items, progress_bar, processed_ids):
    card_info_list = []
    for item in database_items.get('results', []):
        properties = item.get('properties', {})
        # Skip cards if "ORGA ID*" is already filled
        orga_id_property = properties.get('ORGA ID*', {})
        if orga_id_property and orga_id_property.get('rich_text'):
            continue

        # Skip cards that have already been processed
        page_id = item['id']
        if page_id in processed_ids:
            continue

        # Get the title of the card
        title_property = next((prop for prop in properties.values() if prop['type'] == 'title'), None)
        if title_property:
            title = ''.join([text['plain_text'] for text in title_property['title']])
        else:
            title = "Title not found"

        # Create a link to the card based on its ID
        link = f"https://www.notion.so/{page_id.replace('-', '')}"

        # Extract the organization ID from the card's blocks
        blocks = get_page_blocks(page_id)
        org_id = extract_org_id_from_blocks(blocks) if blocks else None

        if org_id:
            # Update the card with the found organization ID
            if update_card_property(page_id, org_id):
                # Verify if the update was successful
                if verify_card_property(page_id, org_id):
                    print(f"Card {page_id}'s 'ORGA ID*' was updated with organization ID {org_id}.")
                    card_info_list.append({
                        'Link': link,
                        'Card Title': title,
                        'Org ID': org_id,
                        'Source': 'Corpus'
                    })
                else:
                    print(f"Failed to verify 'ORGA ID*' for card {page_id}.")
            else:
                print(f"Failed to update 'ORGA ID*' for card {page_id}.")

        # Update progress bar
        progress_bar.update(1)
        progress_bar.set_description(f"{progress_bar.n}/{progress_bar.total}")

    return card_info_list

# Function to create a pandas DataFrame from card information
def create_dataframe(card_info_list):
    return pd.DataFrame(card_info_list)

# Main function that handles the entire process of retrieving, processing, and saving the data
def main():
    start_cursor = None
    all_card_info = []
    total_cards = 0

    # Path to the existing CSV file
    csv_path = os.path.join(os.path.expanduser("~"), "Desktop", "V2.csv")  # Updated to a generic path

    # Read the existing CSV to retrieve already processed card IDs
    if os.path.exists(csv_path):
        df_existing = pd.read_csv(csv_path)
        processed_ids = set(df_existing['Link'].str.extract(r'([^/]+)$')[0].values)
    else:
        processed_ids = set()

    # Estimate the total number of cards
    initial_response = get_database_items(DATABASE_ID)
    if initial_response is None:
        print("Error during initial Notion API request.")
        return
    total_cards = initial_response.get('total', 0)

    # Initialize progress bar
    progress_bar = tqdm(total=total_cards, desc="Processing cards", unit="card")

    while True:
        # Fetch cards from the database
        database_items = get_database_items(DATABASE_ID, start_cursor)
        if database_items is None:
            break
        card_info_list = extract_card_info(database_items, progress_bar, processed_ids)
        all_card_info.extend(card_info_list)
        # Check if more pages are available
        if not database_items.get('has_more'):
            break
        start_cursor = database_items.get('next_cursor')

    progress_bar.close()

    # Save extracted card information to CSV
    if all_card_info:
        df = create_dataframe(all_card_info)
        df.to_csv(csv_path, index=False)  # Save to the CSV file
        print(f"Card information has been written to {csv_path}")
        print(f"Number of cards without 'ORGA ID*': {len(all_card_info)}")
    else:
        print("No cards were found without the 'ORGA ID*' property.")

if __name__ == '__main__':
    main()
