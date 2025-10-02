#!/usr/bin/env python3
import argparse
import os
import sys
from pathlib import Path

import requests


def upload_csv(filepath, project_id, api_token, api_url, generate_after_upload):
    """
    Upload a CSV file to the API endpoint.

    Args:
        filepath (str): Path to the CSV file to upload
        project_id (int): Project ID to upload to
        api_token (str): API project token for authentication
        api_url (str): Base URL of the API
        generate_after_upload (bool): Start generation after upload.

    Returns:
        bool: True if successful, False otherwise
    """
    if not os.path.exists(filepath):
        print(f"Error: File not found: {filepath}")
        return False

    try:
        # Prepare headers with Bearer token
        headers = {
            "Authorization": f"Bearer {api_token}",
        }

        # Prepare the multipart form data
        files = {"csv_file": open(filepath, "rb")}
        data = {
            "project_id": str(project_id),
            "generate_after_upload": generate_after_upload,
        }

        # Make the request
        endpoint = f"{api_url.rstrip('/')}/api/v1/upload/csv/"
        response = requests.post(endpoint, headers=headers, data=data, files=files)

        # Check response
        if response.status_code == 200:
            result = response.json()
            print(f"Success! Upload successful: {result['data']['original_filename']}")
            print(f"API Session ID: {result['data']['api_session_id']}")
            return True
        else:
            print(f"Error: Upload failed with status code {response.status_code}")
            print(f"Response: {response.text}")
            return False

    except requests.exceptions.RequestException as e:
        print(f"Error: Failed to connect to server: {e}")
        return False
    except Exception as e:
        print(f"Error: {str(e)}")
        return False
    finally:
        # Ensure file is closed
        if "files" in locals():
            files["csv_file"].close()


def main():
    parser = argparse.ArgumentParser(description="Upload a CSV file to the API")
    parser.add_argument("filepath", type=str, help="Path to the CSV file to upload")
    parser.add_argument(
        "--project-id",
        type=int,
        help="Project ID to upload to",
        default=os.environ.get("PROJECT_ID"),
    )
    parser.add_argument(
        "--api-token",
        type=str,
        help="API token for Bearer authentication",
        default=os.environ.get("API_TOKEN"),
    )
    parser.add_argument(
        "--api-url",
        type=str,
        help="Base URL of the API",
        default=os.environ.get("API_URL", "http://localhost:8000"),
    )
    parser.add_argument(
        "--generate-after-upload",
        type=bool,
        help="Start generation after upload completes",
        default=False,
    )

    args = parser.parse_args()

    # Validate required arguments
    if not args.project_id:
        print(
            "Error: Project ID is required. "
            "Provide it via --project-id or set PROJECT_ID "
            "environment variable"
        )
        sys.exit(1)

    if not args.api_token:
        print(
            "Error: API token is required. "
            "Provide it via --api-token or set API_TOKEN "
            "environment variable"
        )
        sys.exit(1)

    # Normalize filepath
    filepath = str(Path(args.filepath).expanduser().resolve())

    # Attempt upload
    success = upload_csv(
        filepath,
        args.project_id,
        args.api_token,
        args.api_url,
        args.generate_after_upload,
    )
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
