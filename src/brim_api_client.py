"""
BRIM API Client Module
======================

Interact with BRIM Health API for automated extraction jobs.

NOTE: This is a template implementation. Actual API endpoints, authentication,
and parameters will need to be confirmed with BRIM documentation or support.
"""

import requests
import time
from typing import Dict, Optional, Any, List
from pathlib import Path
import json


class BRIMAPIClient:
    """
    Client for BRIM Health API automation.
    
    Handles:
    - Authentication
    - File uploads (project, variables, decisions CSVs)
    - Job submission and monitoring
    - Results download
    """
    
    def __init__(self, api_key: str, base_url: str = "https://api.brimhealth.com/v1"):
        """
        Initialize BRIM API client.
        
        Args:
            api_key: BRIM API key (get from account settings)
            base_url: BRIM API base URL
        """
        self.api_key = api_key
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {api_key}',
            'User-Agent': 'RADIANT-BRIM-Analytics/0.1.0'
        })
    
    def test_connection(self) -> bool:
        """
        Test API connectivity and authentication.
        
        Returns:
            True if connection successful
        """
        try:
            response = self.session.get(f"{self.base_url}/health")
            response.raise_for_status()
            print("✓ BRIM API connection successful")
            return True
        except requests.exceptions.RequestException as e:
            print(f"✗ BRIM API connection failed: {e}")
            return False
    
    def create_project(self, name: str, description: str = "") -> str:
        """
        Create a new BRIM project.
        
        Args:
            name: Project name
            description: Optional project description
            
        Returns:
            Project ID
        """
        payload = {
            'name': name,
            'description': description
        }
        
        response = self.session.post(
            f"{self.base_url}/projects",
            json=payload
        )
        response.raise_for_status()
        
        project_id = response.json()['project_id']
        print(f"✓ Created project: {project_id}")
        return project_id
    
    def upload_project_csv(self, project_id: str, file_path: str) -> bool:
        """
        Upload project CSV (clinical notes).
        
        Args:
            project_id: BRIM project ID
            file_path: Path to project CSV
            
        Returns:
            True if successful
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            raise FileNotFoundError(f"Project CSV not found: {file_path}")
        
        with open(file_path, 'rb') as f:
            files = {'file': (file_path.name, f, 'text/csv')}
            response = self.session.post(
                f"{self.base_url}/projects/{project_id}/data",
                files=files
            )
        
        response.raise_for_status()
        print(f"✓ Uploaded project CSV: {file_path.name}")
        return True
    
    def upload_variables_csv(self, project_id: str, file_path: str) -> bool:
        """
        Upload variables configuration CSV.
        
        Args:
            project_id: BRIM project ID
            file_path: Path to variables CSV
            
        Returns:
            True if successful
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            raise FileNotFoundError(f"Variables CSV not found: {file_path}")
        
        with open(file_path, 'rb') as f:
            files = {'file': (file_path.name, f, 'text/csv')}
            response = self.session.post(
                f"{self.base_url}/projects/{project_id}/variables",
                files=files
            )
        
        response.raise_for_status()
        print(f"✓ Uploaded variables CSV: {file_path.name}")
        return True
    
    def upload_decisions_csv(self, project_id: str, file_path: str) -> bool:
        """
        Upload dependent variables configuration CSV.
        
        Args:
            project_id: BRIM project ID
            file_path: Path to decisions CSV
            
        Returns:
            True if successful
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            raise FileNotFoundError(f"Decisions CSV not found: {file_path}")
        
        with open(file_path, 'rb') as f:
            files = {'file': (file_path.name, f, 'text/csv')}
            response = self.session.post(
                f"{self.base_url}/projects/{project_id}/decisions",
                files=files
            )
        
        response.raise_for_status()
        print(f"✓ Uploaded decisions CSV: {file_path.name}")
        return True
    
    def submit_extraction_job(
        self, 
        project_id: str, 
        config: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Submit extraction job for processing.
        
        Args:
            project_id: BRIM project ID
            config: Optional job configuration
            
        Returns:
            Job ID
        """
        payload = config or {}
        payload['project_id'] = project_id
        
        response = self.session.post(
            f"{self.base_url}/jobs/extract",
            json=payload
        )
        response.raise_for_status()
        
        job_id = response.json()['job_id']
        print(f"✓ Submitted extraction job: {job_id}")
        return job_id
    
    def get_job_status(self, job_id: str) -> Dict[str, Any]:
        """
        Get current job status.
        
        Args:
            job_id: BRIM job ID
            
        Returns:
            Job status dict with keys: status, progress, message
        """
        response = self.session.get(
            f"{self.base_url}/jobs/{job_id}"
        )
        response.raise_for_status()
        
        return response.json()
    
    def wait_for_completion(
        self, 
        job_id: str, 
        poll_interval: int = 30,
        timeout: int = 7200  # 2 hours default
    ) -> Dict[str, Any]:
        """
        Poll job status until completion or timeout.
        
        Args:
            job_id: BRIM job ID
            poll_interval: Seconds between status checks
            timeout: Maximum seconds to wait
            
        Returns:
            Final job status dict
        """
        start_time = time.time()
        last_status = None
        
        print(f"⏳ Waiting for job {job_id} to complete...")
        
        while True:
            elapsed = time.time() - start_time
            
            if elapsed > timeout:
                raise TimeoutError(
                    f"Job {job_id} did not complete within {timeout/60:.1f} minutes"
                )
            
            status = self.get_job_status(job_id)
            current_status = status.get('status')
            
            # Print status updates
            if current_status != last_status:
                progress = status.get('progress', 0)
                message = status.get('message', '')
                print(f"  Status: {current_status} ({progress}%) - {message}")
                last_status = current_status
            
            # Check terminal states
            if current_status == 'completed':
                print(f"✓ Job completed successfully in {elapsed/60:.1f} minutes")
                return status
            
            elif current_status == 'failed':
                error = status.get('error', 'Unknown error')
                raise Exception(f"Job {job_id} failed: {error}")
            
            elif current_status == 'cancelled':
                raise Exception(f"Job {job_id} was cancelled")
            
            # Wait before next poll
            time.sleep(poll_interval)
    
    def download_results(
        self, 
        job_id: str, 
        output_path: str,
        result_format: str = 'csv'
    ) -> str:
        """
        Download extraction results.
        
        Args:
            job_id: BRIM job ID
            output_path: Where to save results
            result_format: Format ('csv', 'json', 'excel')
            
        Returns:
            Path to downloaded file
        """
        output_path = Path(output_path)
        
        params = {'format': result_format}
        response = self.session.get(
            f"{self.base_url}/jobs/{job_id}/results",
            params=params,
            stream=True
        )
        response.raise_for_status()
        
        # Write to file
        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        
        file_size = output_path.stat().st_size / (1024 * 1024)  # MB
        print(f"✓ Downloaded results: {output_path} ({file_size:.2f} MB)")
        
        return str(output_path)
    
    def get_extraction_summary(self, job_id: str) -> Dict[str, Any]:
        """
        Get extraction summary statistics.
        
        Args:
            job_id: BRIM job ID
            
        Returns:
            Summary dict with extraction metrics
        """
        response = self.session.get(
            f"{self.base_url}/jobs/{job_id}/summary"
        )
        response.raise_for_status()
        
        return response.json()
    
    def cancel_job(self, job_id: str) -> bool:
        """
        Cancel a running job.
        
        Args:
            job_id: BRIM job ID
            
        Returns:
            True if cancelled successfully
        """
        response = self.session.post(
            f"{self.base_url}/jobs/{job_id}/cancel"
        )
        response.raise_for_status()
        
        print(f"✓ Cancelled job: {job_id}")
        return True
    
    def list_projects(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        List all projects in account.
        
        Args:
            limit: Maximum number of projects to return
            
        Returns:
            List of project dicts
        """
        params = {'limit': limit}
        response = self.session.get(
            f"{self.base_url}/projects",
            params=params
        )
        response.raise_for_status()
        
        return response.json()['projects']
    
    def delete_project(self, project_id: str) -> bool:
        """
        Delete a project and all associated data.
        
        Args:
            project_id: BRIM project ID
            
        Returns:
            True if deleted successfully
        """
        response = self.session.delete(
            f"{self.base_url}/projects/{project_id}"
        )
        response.raise_for_status()
        
        print(f"✓ Deleted project: {project_id}")
        return True


def run_complete_workflow(
    project_csv: str,
    variables_csv: str,
    decisions_csv: str,
    api_key: str,
    project_name: str,
    output_dir: str = "."
) -> Dict[str, Any]:
    """
    Run complete BRIM extraction workflow.
    
    Args:
        project_csv: Path to BRIM project CSV
        variables_csv: Path to variables CSV
        decisions_csv: Path to decisions CSV
        api_key: BRIM API key
        project_name: Name for BRIM project
        output_dir: Directory for results
        
    Returns:
        Dict with project_id, job_id, results_path
    """
    
    client = BRIMAPIClient(api_key)
    
    # Test connection
    if not client.test_connection():
        raise ConnectionError("Failed to connect to BRIM API")
    
    # Create project
    print(f"\n📁 Creating project: {project_name}")
    project_id = client.create_project(project_name)
    
    # Upload files
    print(f"\n📤 Uploading files...")
    client.upload_project_csv(project_id, project_csv)
    client.upload_variables_csv(project_id, variables_csv)
    client.upload_decisions_csv(project_id, decisions_csv)
    
    # Submit job
    print(f"\n🚀 Submitting extraction job...")
    job_id = client.submit_extraction_job(project_id)
    
    # Wait for completion
    print(f"\n⏳ Processing...")
    result = client.wait_for_completion(job_id, poll_interval=30)
    
    # Download results
    print(f"\n📥 Downloading results...")
    output_path = Path(output_dir) / f"brim_results_{job_id}.csv"
    results_file = client.download_results(job_id, str(output_path))
    
    # Get summary
    print(f"\n📊 Extraction Summary:")
    summary = client.get_extraction_summary(job_id)
    for key, value in summary.items():
        print(f"  {key}: {value}")
    
    return {
        'project_id': project_id,
        'job_id': job_id,
        'results_path': results_file,
        'summary': summary
    }
