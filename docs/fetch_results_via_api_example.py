#!/usr/bin/env python3
import argparse
import json
import os
import re
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

import requests


class TaskStatus:
    """Enumeration of task status values."""

    WAITING, RUNNING, COMPLETE, ERROR, STOPPED = range(5)

    LABELS = {
        WAITING: "Waiting",
        RUNNING: "Running",
        COMPLETE: "Complete",
        ERROR: "Error",
        STOPPED: "Stopped",
    }


class FetchResultsClient:
    """Client for interacting with the Results API to retrieve CSV exports."""

    def __init__(self, base_url, token, verbose=False):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.endpoint = f"{self.base_url}/api/v1/results/"
        self.verbose = verbose
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
                "Accept": "*/*",
            }
        )

    def log(self, message, always=False):
        """Log message based on verbosity setting."""
        if self.verbose or always:
            print(message)

    def fetch_results(
        self,
        project_id,
        api_session_id=None,
        detailed_export=False,
        patient_export=False,
        include_null_in_export=True,
        output_path=None,
        max_retries=30,
        retry_interval=5,
    ):
        """
        Fetch results from the API and save to file.

        Args:
            project_id: ID of the project
            api_session_id: Optional ID used to control export scope or poll status:
                - None: Export data for the entire project (all patients/documents)
                - Upload task ID: Export only data from documents in that specific upload
                - Generate task ID: Export only data from documents processed from generation run
                - Export task ID: Check status or retrieve results of a previously initiated export
            detailed_export: Whether to request detailed export format
            patient_export: Whether to request patient export format
            include_null_in_export: Whether to include null values
            output_path: Path to save the CSV file
            max_retries: Maximum number of polling attempts
            retry_interval: Seconds between polling attempts

        Returns:
            Path to saved file or status information dictionary
        """
        self.current_project_id = project_id

        payload = {
            "project_id": str(project_id),
            "detailed_export": detailed_export,
            "patient_export": patient_export,
            "include_null_in_export": include_null_in_export,
        }

        # Only include api_session_id in payload if provided
        # - When omitted: Creates export for entire project
        # - When included: Creates filtered export or polls existing export
        if api_session_id:
            payload["api_session_id"] = api_session_id

        return self._poll_until_complete(
            payload, output_path, max_retries, retry_interval
        )

    def _make_request(self, payload):
        """Make a POST request to the API endpoint."""
        self.log(
            f"Making request to {self.endpoint} with payload: {json.dumps(payload, indent=2)}"
        )

        try:
            response = self.session.post(
                self.endpoint,
                json=payload,
                stream=True,  # Important for handling large files
            )

            self.log(f"Response status: {response.status_code}")
            self.log(
                f"Response content type: {response.headers.get('Content-Type', 'unknown')}"
            )

            # Preview response content when verbose
            if self.verbose and "text/csv" not in response.headers.get(
                "Content-Type", ""
            ):
                self._preview_response(response)

            response.raise_for_status()  # Raise HTTPError for bad responses
            return response

        except requests.exceptions.RequestException as e:
            self._handle_request_error(e)

    def _preview_response(self, response):
        """Preview non-CSV response content when in verbose mode."""
        try:
            if "application/json" in response.headers.get("Content-Type", ""):
                response_preview = json.dumps(response.json(), indent=2)
                self.log(f"Response preview: {response_preview}")
            else:
                # Show raw text preview with limited length
                content_preview = response.text[:500]
                self.log(f"Response content preview: {content_preview}")
        except Exception as e:
            self.log(f"Could not preview response: {e}")

    def _handle_request_error(self, error):
        """Handle request exceptions with helpful error messages."""
        print(f"\nError making request: {error}")

        if hasattr(error, "response") and error.response is not None:
            print(f"Response status code: {error.response.status_code}")
            try:
                # Try to parse error response as JSON
                error_content = error.response.json()
                print(f"Error details: {json.dumps(error_content, indent=2)}")
            except ValueError:
                # If not JSON, print raw text
                print(f"Error content: {error.response.text[:500]}")

        sys.exit(1)  # Exit on request error

    def sanitize_filename(self, filename):
        """
        Sanitize the filename to prevent path traversal and other security issues.

        Args:
            filename: The original filename

        Returns:
            A sanitized version of the filename
        """
        if not filename:
            return ""

        # Replace any potentially dangerous characters
        sanitized = re.sub(r'[\\/*?:"<>|]', "_", filename)
        # Ensure the filename doesn't start with dots or slashes
        sanitized = re.sub(r"^[./\\]+", "", sanitized)
        return sanitized

    def sanitize_filepath(self, filepath):
        """
        Custom implementation of filepath sanitization without external dependency.

        Args:
            filepath: The original filepath

        Returns:
            A sanitized version of the filepath
        """
        if not filepath:
            return ""

        # Handle path components separately
        path_parts = Path(filepath).parts
        sanitized_parts = []

        for part in path_parts:
            # Replace dangerous characters
            sanitized = re.sub(r'[\\/*?:"<>|]', "_", part)
            # Handle special cases for directory traversal
            if sanitized in ("..", "."):
                sanitized = "_" + sanitized
            sanitized_parts.append(sanitized)

        # Reconstruct the path
        return str(Path(*sanitized_parts))

    def ensure_safe_path(self, base_path, user_path):
        """
        Ensures a user-provided path cannot escape from the base path
        through directory traversal.

        Args:
            base_path: The allowed base directory
            user_path: User-provided path that needs validation

        Returns:
            A safe absolute path that is guaranteed to be within base_path
        """
        # Normalize paths
        base_path = os.path.normpath(os.path.abspath(base_path))

        # Join and normalize the combined path
        full_path = os.path.normpath(os.path.join(base_path, user_path))

        # Check if the normalized path starts with the base path
        if not full_path.startswith(base_path):
            # If there's an escape attempt, return the base path instead
            return base_path

        return full_path

    def _save_csv(self, response, output_path=None):
        """Save the CSV response to a file using standard Python I/O."""
        filename = self._get_filename_from_response(response)
        sanitized_filename = self.sanitize_filename(filename)
        filepath = self._build_output_path(sanitized_filename, output_path)

        # Additional security: ensure path is safe
        base_dir = (
            os.path.dirname(os.path.abspath(filepath))
            if os.path.dirname(filepath)
            else os.getcwd()
        )
        safe_filepath = self.ensure_safe_path(base_dir, os.path.basename(filepath))

        self._ensure_directory_exists(safe_filepath)

        file_size = 0
        try:
            # Use a temporary file path while writing to ensure atomic writes
            temp_filepath = f"{safe_filepath}.tmp"

            with open(temp_filepath, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:  # Filter out keep-alive chunks
                        f.write(chunk)
                        file_size += len(chunk)

            # Move the temp file to the final location (atomic on most filesystems)
            shutil.move(temp_filepath, safe_filepath)

            self.log(f"\nCSV file saved to: {safe_filepath} ({file_size} bytes)")
            return safe_filepath
        except Exception as e:
            print(f"\nError writing file {safe_filepath}: {e}")
            sys.exit(1)

    def _get_filename_from_response(self, response):
        """Extract filename from response headers or generate a default."""
        content_disposition = response.headers.get("Content-Disposition")
        if not content_disposition:
            return self._generate_default_filename()

        # Try to extract from Content-Disposition header using regex
        for pattern in [r"filename\*=UTF-8''([^;]+)", r'filename="([^"]+)"']:
            match = re.search(pattern, content_disposition)
            if match:
                return requests.utils.unquote(match.group(1))

        # Fall back to generated name
        return self._generate_default_filename()

    def sanitize_name(self, name):
        """
        Sanitizes a name by:
        - Converting to lowercase
        - Replacing spaces and special chars with underscores
        - Removing any non-alphanumeric/underscore chars

        Args:
            name: The original name string

        Returns:
            A sanitized version of the name
        """
        if not name:
            return ""
        # Convert to lowercase and replace spaces/special chars with underscore
        s = re.sub(r"[^\w\s-]", "_", str(name).lower())
        # Replace multiple underscores with single underscore
        s = re.sub(r"[-\s]+", "_", s)
        # Remove leading/trailing underscores
        return s.strip("_")

    def _generate_default_filename(self):
        """
        Generate a default filename with project name and date in format
        ProjectName_extract_YYYY-MM-DD.csv.
        """
        date_now = datetime.now()
        formatted_date = date_now.strftime("%Y-%m-%d")

        project_identifier = getattr(self, "current_project_id", "unknown")

        # Sanitize and truncate to 20 characters as in original code
        safe_project_name = self.sanitize_name(project_identifier)[:20]

        return f"{safe_project_name}_extract_{formatted_date}.csv"

    def _build_output_path(self, filename, output_path=None):
        """Build the complete output filepath."""
        if not output_path:
            # Default to current working directory
            return os.path.join(os.getcwd(), filename)

        # Sanitize the output path
        output_path = self.sanitize_filepath(output_path)

        # Convert to Path object for safer path manipulation
        output_path = Path(output_path)

        # If it's a directory, join with filename
        if output_path.exists() and output_path.is_dir():
            return os.path.join(output_path, filename)

        # If output_path ends with .csv, use it directly
        if str(output_path).lower().endswith((".csv", ".txt")):
            return str(output_path)

        # Otherwise, treat as directory and join with filename
        return os.path.join(output_path, filename)

    def _ensure_directory_exists(self, filepath):
        """Ensure the directory for the file exists."""
        directory = os.path.dirname(filepath)
        if directory:
            # Sanitize the directory path
            directory = self.sanitize_filepath(directory)

            # Additional security check: ensure it's not trying to create directories
            # outside allowed areas
            base_dir = os.getcwd()
            safe_dir = self.ensure_safe_path(base_dir, directory)

            if not os.path.exists(safe_dir):
                try:
                    os.makedirs(safe_dir, exist_ok=True)
                    self.log(f"Created directory: {safe_dir}")
                except Exception as e:
                    print(f"Error creating directory {safe_dir}: {e}")
                    sys.exit(1)

    def _poll_until_complete(self, payload, output_path, max_retries, retry_interval):
        """
        Poll the API until a result is ready or max retries is reached.

        This method handles the task lifecycle:
        1. If this is a new export request (no api_session_id or upload/generate task ID):
        - The server creates a new export task
        - Returns the new export task ID in the response
        2. If this is a subset export request (api_session_id = upload/generate task ID):
        - The server creates a new export task filtered to that source task
        - Returns the new export task ID in the response
        3. If this is a polling request (api_session_id = export task ID):
        - The server checks if the export is ready
        - Returns task status or the CSV file if complete

        In all cases, we use the export task ID from the response for subsequent polling,
        not the original input ID that may have been an upload/generate task ID.
        """
        retries = 0
        # Track the current api_session_id which may change after initial request
        current_api_session_id = payload.get("api_session_id")
        last_status_display = None

        while retries < max_retries:
            # Update API session ID if we have one
            # We need to use the export task ID returned in the first response
            # for all subsequent polling, not the original upload/generate task ID
            # that may have been provided initially
            if current_api_session_id:
                payload["api_session_id"] = current_api_session_id

            response = self._make_request(payload)

            # If we got a CSV, save it and return
            if "text/csv" in response.headers.get("Content-Type", ""):
                self.log("\nCSV file received!", always=True)
                return self._save_csv(response, output_path)

            # Process JSON status response
            response_data = response.json()
            data = response_data.get("data", {})

            # Update task ID for next poll if provided
            # If we provided an upload/generate task ID initially,
            # the server will create a new export task and return its ID here.
            # We must use this new ID for subsequent polls.
            next_api_session_id = data.get("api_session_id")
            if next_api_session_id:
                current_api_session_id = next_api_session_id

            # Display status update if changed
            status_display = data.get("status_display")
            if status_display != last_status_display:
                self._display_status(data.get("status"), status_display)
                last_status_display = status_display

            if data.get("is_complete", False):
                return self._handle_task_completion(
                    response_data, current_api_session_id, payload
                )

            # Wait before next poll
            time.sleep(retry_interval)
            retries += 1

        # Max retries exceeded
        print(
            f"\nError: Maximum retries ({max_retries}) reached without task completion."
        )
        sys.exit(1)

    def _display_status(self, status_code, status_display=None):
        """Display current task status."""
        status_text = status_display or TaskStatus.LABELS.get(status_code, "Unknown")
        print(f"\rTask status: {status_text}...", end="")
        sys.stdout.flush()  # Ensure it prints immediately

    def _handle_task_completion(self, response_data, task_id, payload):
        """Handle a completed task (success or error)."""
        message = response_data.get("message", "Task complete")
        print(f"\n{message}")

        # Check for error status
        if (
            response_data.get("status") == "error"
            or "error" in message.lower()
            or "failed" in message.lower()
        ):
            print("\nExport failed. This may be because:")
            print("- A generate task is still running for this project")
            print("- No data is available to export yet")
            print("- The server encountered an error during export")

            # If this was an upload task, suggest waiting
            if task_id and "upload" in str(task_id).lower():
                print(
                    "\nTIP: For upload tasks, wait for any associated generate tasks to complete before exporting."  # noqa E501
                )

            sys.exit(1)

        # Return task completion info
        return {
            "status": "complete_no_csv",
            "message": message,
            "project_id": payload["project_id"],
            "task_id": task_id,
        }


def main():
    parser = argparse.ArgumentParser(description="Fetch Results API Client")

    # Required arguments with environment variable defaults
    parser.add_argument(
        "--url",
        help="Base URL of the API",
        default=os.environ.get("API_URL", "http://localhost:8000"),
    )
    parser.add_argument(
        "--token", help="API Bearer token", default=os.environ.get("API_TOKEN")
    )
    parser.add_argument(
        "--project-id", help="Project ID", default=os.environ.get("PROJECT_ID")
    )

    # Export type (mutually exclusive)
    export_type = parser.add_mutually_exclusive_group()
    export_type.add_argument(
        "--detailed", action="store_true", help="Request detailed export"
    )
    export_type.add_argument(
        "--patient", action="store_true", help="Request patient export"
    )

    # Null handling
    null_group = parser.add_mutually_exclusive_group()
    null_group.add_argument(
        "--include-null",
        action="store_true",
        default=True,
        help="Include null values (default)",
    )
    null_group.add_argument(
        "--exclude-null", action="store_true", help="Exclude null values"
    )

    # Other options
    parser.add_argument(
        "--api-session-id",
        help="Task ID to poll (if not provided, a new export is initiated)",
        default=os.environ.get("API_SESSION_ID"),
    )
    parser.add_argument(
        "--output-path",
        help="Output filepath or directory for the CSV file",
        default=os.environ.get("OUTPUT_PATH", "."),
    )
    parser.add_argument(
        "--retries",
        type=int,
        help="Max polling attempts",
        default=int(os.environ.get("MAX_RETRIES", "30")),
    )
    parser.add_argument(
        "--interval",
        type=int,
        help="Polling interval in seconds",
        default=int(os.environ.get("RETRY_INTERVAL", "5")),
    )
    parser.add_argument("--verbose", action="store_true", help="Verbose output")

    args = parser.parse_args()

    # Validate required arguments
    if not args.project_id:
        print("Error: Project ID is required (--project-id or PROJECT_ID env var)")
        sys.exit(1)

    if not args.token:
        print("Error: API token is required (--token or API_TOKEN env var)")
        sys.exit(1)

    # Create client and fetch results
    client = FetchResultsClient(args.url, args.token, verbose=args.verbose)

    filepath = client.fetch_results(
        project_id=args.project_id,
        api_session_id=args.api_session_id,
        detailed_export=args.detailed,
        patient_export=args.patient,
        include_null_in_export=not args.exclude_null,
        output_path=args.output_path,
        max_retries=args.retries,
        retry_interval=args.interval,
    )

    # Success
    if isinstance(filepath, str):
        print(f"Operation completed successfully. File saved to: {filepath}")
    else:
        print("Operation completed, but no file was saved.")
    sys.exit(0)


if __name__ == "__main__":
    main()
