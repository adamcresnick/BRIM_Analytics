"""
Binary File Agent - Streams and extracts text from S3-stored binary files

This agent:
1. Queries v_binary_files to get binary file metadata and IDs
2. Constructs S3 paths from binary IDs
3. Streams binary content from S3 (no local storage)
4. Extracts text from PDF/HTML/images (using AWS Textract OCR for images)
5. Returns structured text with metadata for MedGemmaAgent extraction

Supported formats (prioritized):
- Priority 1: text/html, text/plain, text/rtf, text/xml, application/xml (fast, free)
- Priority 2: application/pdf (fast, free)
- Priority 3: image/tiff, image/jpeg, image/png (slow, AWS Textract cost ~$1.50/1000 pages)

NULL content_type handling:
- If content_type is NULL but dr_type_text contains clinical keywords
  (operative, surgery, pathology, imaging, radiation, discharge, etc.),
  the agent will attempt Textract OCR extraction as a fallback.
- This captures scanned documents from outside hospitals that lack proper metadata.
"""

import boto3
import io
import json
import base64
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import fitz  # PyMuPDF - more robust than PyPDF2
from bs4 import BeautifulSoup
from PIL import Image

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class BinaryFileMetadata:
    """Metadata for a binary file"""
    binary_id: str
    document_reference_id: str
    patient_fhir_id: str
    content_type: str
    dr_type_text: Optional[str]
    dr_category_text: Optional[str]
    dr_description: Optional[str]
    dr_date: Optional[str]
    age_at_document_days: Optional[int]
    s3_bucket: str
    s3_key: str


@dataclass
class ExtractedBinaryContent:
    """Extracted text content from binary file"""
    binary_id: str
    document_reference_id: str
    content_type: str
    extracted_text: str
    text_length: int
    extraction_success: bool
    extraction_error: Optional[str]
    metadata: BinaryFileMetadata


class BinaryFileAgent:
    """
    Agent for streaming and extracting text from S3-stored binary files
    """

    def __init__(
        self,
        s3_bucket: str = "radiant-prd-343218191717-us-east-1-prd-ehr-pipeline",
        s3_prefix: str = "prd/source/Binary/",
        aws_profile: Optional[str] = "radiant-prod",
        region_name: str = "us-east-1"
    ):
        """
        Initialize Binary File Agent

        Args:
            s3_bucket: S3 bucket containing binary files
            s3_prefix: Prefix for binary files in S3
            aws_profile: AWS profile name
            region_name: AWS region

        Note:
            Critical S3 naming bug: FHIR Binary IDs contain periods (.) but
            S3 files use underscores (_). This conversion is handled in construct_s3_path().
        """
        self.s3_bucket = s3_bucket
        self.s3_prefix = s3_prefix
        self.region_name = region_name
        self.aws_profile = aws_profile  # Store for token refresh

        # Initialize S3 and Textract clients
        if aws_profile:
            session = boto3.Session(profile_name=aws_profile, region_name=region_name)
            self.s3_client = session.client('s3')
            self.textract_client = session.client('textract')
        else:
            self.s3_client = boto3.client('s3', region_name=region_name)
            self.textract_client = boto3.client('textract', region_name=region_name)

        logger.info(f"BinaryFileAgent initialized: s3://{s3_bucket}/{s3_prefix}")
        logger.info(f"  ✅ AWS Textract enabled for TIFF/image extraction")

    def construct_s3_path(self, binary_id: str) -> Tuple[str, str]:
        """
        Construct S3 bucket and key from binary_id

        Critical S3 Naming Bug Fix:
        - FHIR Binary IDs contain periods (.)
        - S3 files use underscores (_)
        - Example: Binary/fmAXdcPPNkiCF9rr.5soVBQ → prd/source/Binary/fmAXdcPPNkiCF9rr_5soVBQ

        Args:
            binary_id: FHIR binary ID (e.g., "Binary/fmAXdcPPNkiCF9rr5soVBQ...")

        Returns:
            Tuple of (bucket, key)
        """
        # Remove "Binary/" prefix if present
        if binary_id.startswith("Binary/"):
            file_id = binary_id.replace("Binary/", "")
        else:
            file_id = binary_id

        # Apply period-to-underscore conversion (critical S3 bug fix)
        s3_file_id = file_id.replace('.', '_')

        # Construct S3 key
        s3_key = f"{self.s3_prefix}{s3_file_id}"

        return self.s3_bucket, s3_key

    def _refresh_s3_client(self):
        """
        Refresh S3 client with new AWS SSO credentials

        This is called when TokenRetrievalError is detected, which happens
        when AWS SSO tokens expire (typically after 8-12 hours).

        This method actually refreshes the SSO token by running 'aws sso login'
        which opens a browser for user authentication.
        """
        import subprocess

        try:
            logger.info("AWS SSO token expired. Refreshing credentials...")
            if hasattr(self, 'aws_profile') and self.aws_profile:
                print(f"\n{'='*80}")
                print("⚠️  AWS SSO TOKEN EXPIRED DURING EXTRACTION")
                print(f"{'='*80}")
                print(f"Opening browser for AWS SSO login (profile: {self.aws_profile})...")
                print("Please complete the authentication in your browser.")
                print(f"{'='*80}\n")

                # Run aws sso login to refresh the token via browser
                result = subprocess.run(
                    ['aws', 'sso', 'login', '--profile', self.aws_profile],
                    capture_output=True,
                    text=True,
                    timeout=300  # 5 minute timeout for user to complete login
                )

                if result.returncode == 0:
                    # Create new session with refreshed token
                    session = boto3.Session(profile_name=self.aws_profile, region_name=self.region_name)
                    self.s3_client = session.client('s3')
                    logger.info("✅ Successfully refreshed AWS SSO credentials and S3 client")
                    print(f"\n{'='*80}")
                    print("✅ AWS SSO TOKEN REFRESHED - Extraction resuming...")
                    print(f"{'='*80}\n")
                else:
                    error_msg = f"Failed to refresh AWS SSO token: {result.stderr}"
                    logger.error(error_msg)
                    print(f"\n❌ {error_msg}\n")
                    raise Exception(error_msg)
            else:
                logger.warning("No AWS profile configured, cannot refresh credentials")
                raise Exception("No AWS profile configured for SSO refresh")
        except subprocess.TimeoutExpired:
            error_msg = "AWS SSO login timed out after 5 minutes"
            logger.error(error_msg)
            print(f"\n❌ {error_msg}\n")
            print("Please run 'aws sso login --profile radiant-prod' manually and restart extraction.\n")
            raise Exception(error_msg)
        except FileNotFoundError:
            error_msg = "AWS CLI not found. Please install AWS CLI."
            logger.error(error_msg)
            print(f"\n❌ {error_msg}\n")
            raise Exception(error_msg)
        except Exception as e:
            logger.error(f"Failed to refresh AWS credentials: {e}")
            raise

    def stream_binary_from_s3(
        self,
        binary_id: str,
        max_size_mb: int = 50,
        max_retries: int = 1
    ) -> Optional[bytes]:
        """
        Stream binary content from S3 without saving to disk

        IMPORTANT: S3 objects are FHIR Binary resources (JSON with base64-encoded content),
        NOT raw PDFs. This method extracts the actual PDF/HTML from the FHIR wrapper.

        Args:
            binary_id: FHIR binary ID
            max_size_mb: Maximum file size to stream (MB)
            max_retries: Number of times to retry on token expiration (default: 1)

        Returns:
            Binary content as bytes (actual PDF/HTML, not FHIR JSON), or None if error
        """
        bucket, key = self.construct_s3_path(binary_id)

        for attempt in range(max_retries + 1):
            try:
                logger.info(f"Streaming from s3://{bucket}/{key}")

                # Get object metadata first to check size
                response = self.s3_client.head_object(Bucket=bucket, Key=key)
                file_size_bytes = response['ContentLength']
                file_size_mb = file_size_bytes / (1024 * 1024)

                if file_size_mb > max_size_mb:
                    logger.warning(
                        f"File too large: {file_size_mb:.2f}MB > {max_size_mb}MB limit. "
                        f"Skipping {binary_id}"
                    )
                    return None

                # Stream the FHIR Binary resource (JSON)
                response = self.s3_client.get_object(Bucket=bucket, Key=key)
                fhir_json = response['Body'].read()

                # Extract base64-encoded content from FHIR Binary resource
                fhir_data = json.loads(fhir_json)

                if 'data' not in fhir_data:
                    logger.error(f"No 'data' field in FHIR Binary resource: {binary_id}")
                    return None

                # Decode base64 to get actual binary content (PDF/HTML/etc)
                binary_content = base64.b64decode(fhir_data['data'])

                logger.info(f"Successfully extracted {len(binary_content)/1024:.1f}KB from FHIR Binary resource")
                return binary_content

            except self.s3_client.exceptions.NoSuchKey:
                logger.error(f"File not found in S3: s3://{bucket}/{key}")
                return None
            except json.JSONDecodeError as e:
                logger.error(f"Invalid FHIR JSON in S3 object: {e}")
                return None
            except Exception as e:
                error_str = str(e)

                # Check if this is a token retrieval error
                if 'TokenRetrievalError' in error_str or 'The SSO session associated with this profile has expired' in error_str:
                    if attempt < max_retries:
                        logger.warning(f"AWS SSO token expired. Refreshing credentials and retrying (attempt {attempt + 1}/{max_retries})...")
                        self._refresh_s3_client()
                        continue
                    else:
                        logger.error(f"AWS SSO token expired and max retries reached. Please run 'aws sso login --profile {getattr(self, 'aws_profile', 'radiant-prod')}'")
                        return None

                logger.error(f"Error streaming from S3: {e}")
                return None

        return None

    def extract_text_from_pdf(self, pdf_content: bytes) -> Tuple[str, Optional[str]]:
        """
        Extract text from PDF bytes using PyMuPDF (fitz)

        PyMuPDF is more robust than PyPDF2 and handles malformed/non-standard PDFs
        better, which is critical for EHR-generated medical reports.

        Args:
            pdf_content: PDF file as bytes

        Returns:
            Tuple of (extracted_text, error_message)
        """
        try:
            # Open PDF from bytes stream
            doc = fitz.open(stream=pdf_content, filetype="pdf")

            text_parts = []
            for page in doc:
                text_parts.append(page.get_text())

            doc.close()

            extracted_text = "\n\n".join(text_parts)
            return extracted_text.strip(), None

        except Exception as e:
            error_msg = f"PDF extraction error: {str(e)}"
            logger.error(error_msg)
            return "", error_msg

    def extract_text_from_html(self, html_content: bytes) -> Tuple[str, Optional[str]]:
        """
        Extract text from HTML bytes

        Args:
            html_content: HTML file as bytes

        Returns:
            Tuple of (extracted_text, error_message)
        """
        try:
            # Try different encodings
            for encoding in ['utf-8', 'latin-1', 'windows-1252']:
                try:
                    html_string = html_content.decode(encoding)
                    break
                except UnicodeDecodeError:
                    continue
            else:
                return "", "Failed to decode HTML with any common encoding"

            # Parse HTML and extract text
            soup = BeautifulSoup(html_string, 'html.parser')

            # Remove script and style elements
            for script in soup(["script", "style"]):
                script.decompose()

            # Get text
            text = soup.get_text()

            # Clean up whitespace
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = '\n'.join(chunk for chunk in chunks if chunk)

            return text, None

        except Exception as e:
            error_msg = f"HTML extraction error: {str(e)}"
            logger.error(error_msg)
            return "", error_msg

    def extract_text_from_image(self, image_content: bytes, image_format: str = "TIFF") -> Tuple[str, Optional[str]]:
        """
        Extract text from image using AWS Textract OCR

        Supports TIFF, JPEG, PNG scanned documents (e.g., outside hospital operative notes,
        radiation therapy summaries, pathology reports) that require OCR to extract text.

        Process:
        1. For TIFF: Convert to PNG (Textract doesn't support TIFF directly)
        2. For JPEG/PNG: Use directly (Textract natively supports these)
        3. Send to AWS Textract detect_document_text API
        4. Extract text from LINE blocks

        Args:
            image_content: Image file as bytes
            image_format: Image format (TIFF, JPEG, PNG) for logging

        Returns:
            Tuple of (extracted_text, error_message)
        """
        try:
            # Determine if we need to convert format
            image_bytes = image_content

            if image_format.upper() in ["TIFF", "TIF"]:
                logger.info("Converting TIFF to PNG for Textract...")
                # Open TIFF with PIL and convert to PNG
                image = Image.open(io.BytesIO(image_content))
                logger.info(f"  TIFF: {image.size} pixels, mode: {image.mode}")

                png_buffer = io.BytesIO()
                image.save(png_buffer, format='PNG')
                image_bytes = png_buffer.getvalue()
                logger.info(f"  Converted to PNG: {len(image_bytes):,} bytes")
            else:
                # JPEG/PNG can be used directly with Textract
                logger.info(f"Using {image_format} directly with Textract (native support)...")
                logger.info(f"  Image size: {len(image_bytes):,} bytes")

            # Call AWS Textract
            logger.info("Calling AWS Textract detect_document_text...")
            textract_response = self.textract_client.detect_document_text(
                Document={'Bytes': image_bytes}
            )

            # Extract text from LINE blocks
            blocks = textract_response.get('Blocks', [])
            lines = [block.get('Text', '') for block in blocks if block['BlockType'] == 'LINE']
            full_text = '\n'.join(lines)

            logger.info(f"  ✅ Textract extracted {len(lines)} lines ({len(full_text)} chars)")

            if len(full_text) == 0:
                return "", f"Textract returned no text from {image_format} image"

            return full_text, None

        except Exception as e:
            error_msg = f"{image_format}/Textract extraction error: {str(e)}"
            logger.error(error_msg)
            return "", error_msg

    def extract_binary_content(
        self,
        metadata: BinaryFileMetadata
    ) -> ExtractedBinaryContent:
        """
        Stream binary file from S3 and extract text content

        Args:
            metadata: Binary file metadata

        Returns:
            ExtractedBinaryContent with text and metadata
        """
        logger.info(f"Extracting content from {metadata.binary_id} ({metadata.content_type})")

        # Stream from S3
        binary_content = self.stream_binary_from_s3(metadata.binary_id)

        if binary_content is None:
            return ExtractedBinaryContent(
                binary_id=metadata.binary_id,
                document_reference_id=metadata.document_reference_id,
                content_type=metadata.content_type,
                extracted_text="",
                text_length=0,
                extraction_success=False,
                extraction_error="Failed to stream from S3",
                metadata=metadata
            )

        # Extract text based on content type
        # Priority: HTML/PDF/text (fast, free) > images (slow, AWS Textract cost)
        extracted_text = ""
        error_msg = None

        # Determine content type (with fallback for NULL based on dr_type_text)
        content_type = metadata.content_type

        # FALLBACK: If content_type is NULL but dr_type_text suggests clinical document, try Textract
        if not content_type or content_type == "":
            dr_type = (metadata.dr_type_text or "").lower()
            if any(keyword in dr_type for keyword in [
                'operative', 'surgery', 'pathology', 'imaging', 'radiology',
                'discharge', 'progress', 'consultation', 'treatment', 'radiation',
                'outside', 'external'
            ]):
                logger.info(f"  NULL content_type but dr_type_text='{metadata.dr_type_text}' - trying Textract OCR")
                content_type = "image/unknown"  # Try as image

        if content_type == "application/pdf":
            extracted_text, error_msg = self.extract_text_from_pdf(binary_content)
        elif content_type in ["text/html", "text/plain", "text/rtf", "text/xml", "application/xml"]:
            # Use HTML parser for all text-based formats (works for XML too)
            extracted_text, error_msg = self.extract_text_from_html(binary_content)
        elif content_type in ["image/tiff", "image/tif"]:
            # Use AWS Textract OCR for TIFF scanned documents
            logger.info("  Using AWS Textract for TIFF OCR (scanned document)")
            extracted_text, error_msg = self.extract_text_from_image(binary_content, "TIFF")
        elif content_type in ["image/jpeg", "image/jpg"]:
            # Use AWS Textract OCR for JPEG scanned documents (native support)
            logger.info("  Using AWS Textract for JPEG OCR (scanned document)")
            extracted_text, error_msg = self.extract_text_from_image(binary_content, "JPEG")
        elif content_type in ["image/png"]:
            # Use AWS Textract OCR for PNG scanned documents (native support)
            logger.info("  Using AWS Textract for PNG OCR (scanned document)")
            extracted_text, error_msg = self.extract_text_from_image(binary_content, "PNG")
        elif content_type == "image/unknown":
            # NULL content_type but clinical dr_type_text - try Textract
            logger.info("  Trying AWS Textract for unknown image type (NULL content_type)")
            extracted_text, error_msg = self.extract_text_from_image(binary_content, "UNKNOWN")
        else:
            error_msg = f"Unsupported content type: {content_type or 'NULL'}"
            if metadata.dr_type_text:
                error_msg += f" (dr_type_text: {metadata.dr_type_text})"
            logger.warning(error_msg)

        success = len(extracted_text) > 0 and error_msg is None

        return ExtractedBinaryContent(
            binary_id=metadata.binary_id,
            document_reference_id=metadata.document_reference_id,
            content_type=metadata.content_type,
            extracted_text=extracted_text,
            text_length=len(extracted_text),
            extraction_success=success,
            extraction_error=error_msg,
            metadata=metadata
        )

    def extract_text_from_binary(
        self,
        binary_id: str,
        patient_fhir_id: str,
        content_type: str = "application/pdf",
        document_reference_id: str = None
    ) -> Tuple[str, Optional[str]]:
        """
        Convenience wrapper for extracting text from a binary file.

        This method provides a simpler interface than extract_binary_content()
        for cases where you have binary_id but not full metadata.

        Args:
            binary_id: Binary resource FHIR ID
            patient_fhir_id: Patient FHIR ID
            content_type: Content type (default: application/pdf)
            document_reference_id: Optional DocumentReference ID

        Returns:
            Tuple of (extracted_text, error_message)
            If successful: (text, None)
            If failed: ("", error_message)
        """
        # Construct S3 path from binary_id
        s3_bucket, s3_key = self.construct_s3_path(binary_id)

        # Create minimal metadata object
        metadata = BinaryFileMetadata(
            binary_id=binary_id,
            document_reference_id=document_reference_id or binary_id,
            patient_fhir_id=patient_fhir_id,
            content_type=content_type,
            dr_type_text=None,
            dr_category_text=None,
            dr_description=None,
            dr_date=None,
            age_at_document_days=None,
            s3_bucket=s3_bucket,
            s3_key=s3_key
        )

        # Use main extraction method
        result = self.extract_binary_content(metadata)

        if result.extraction_success:
            return (result.extracted_text, None)
        else:
            return ("", result.extraction_error)

    def get_imaging_binary_files(
        self,
        athena_client,
        patient_fhir_id: str,
        database: str = "fhir_prd_db",
        output_location: str = "s3://aws-athena-query-results-343218191717-us-east-1/"
    ) -> List[BinaryFileMetadata]:
        """
        Query v_binary_files to get imaging-related binary files for a patient

        Args:
            athena_client: Boto3 Athena client
            patient_fhir_id: Patient FHIR ID
            database: Athena database name
            output_location: S3 location for Athena results

        Returns:
            List of BinaryFileMetadata
        """
        query = f"""
        SELECT
            binary_id,
            document_reference_id,
            patient_fhir_id,
            content_type,
            dr_type_text,
            dr_category_text,
            dr_description,
            dr_date,
            age_at_document_days
        FROM {database}.v_binary_files
        WHERE patient_fhir_id = '{patient_fhir_id}'
        AND dr_type_text = 'Diagnostic imaging study'
        ORDER BY dr_date DESC
        """

        logger.info(f"Querying v_binary_files for patient {patient_fhir_id}")

        # Execute query
        response = athena_client.start_query_execution(
            QueryString=query,
            QueryExecutionContext={'Database': database},
            ResultConfiguration={'OutputLocation': output_location}
        )

        query_id = response['QueryExecutionId']

        # Wait for completion
        import time
        while True:
            result = athena_client.get_query_execution(QueryExecutionId=query_id)
            status = result['QueryExecution']['Status']['State']

            if status == 'SUCCEEDED':
                break
            elif status in ['FAILED', 'CANCELLED']:
                logger.error(f"Query failed: {status}")
                return []

            time.sleep(1)

        # Get results
        results = athena_client.get_query_results(QueryExecutionId=query_id)
        rows = results['ResultSet']['Rows']

        # Parse results into metadata objects
        metadata_list = []
        for row in rows[1:]:  # Skip header
            values = [col.get('VarCharValue') for col in row['Data']]

            binary_id = values[0]
            bucket, key = self.construct_s3_path(binary_id)

            metadata = BinaryFileMetadata(
                binary_id=binary_id,
                document_reference_id=values[1],
                patient_fhir_id=values[2],
                content_type=values[3],
                dr_type_text=values[4],
                dr_category_text=values[5],
                dr_description=values[6],
                dr_date=values[7],
                age_at_document_days=int(values[8]) if values[8] else None,
                s3_bucket=bucket,
                s3_key=key
            )
            metadata_list.append(metadata)

        logger.info(f"Found {len(metadata_list)} binary imaging files")
        return metadata_list


if __name__ == "__main__":
    # Test the agent
    import boto3

    agent = BinaryFileAgent()

    # Initialize Athena client
    session = boto3.Session(profile_name='radiant-prod', region_name='us-east-1')
    athena_client = session.client('athena')

    # Get binary files for test patient
    patient_id = "e4BwD8ZYDBccepXcJ.Ilo3w3"
    metadata_list = agent.get_imaging_binary_files(athena_client, patient_id)

    print(f"\nFound {len(metadata_list)} binary imaging files")

    if metadata_list:
        # Test extraction on first file
        print(f"\nTesting extraction on: {metadata_list[0].binary_id}")
        result = agent.extract_binary_content(metadata_list[0])

        print(f"Success: {result.extraction_success}")
        print(f"Text length: {result.text_length}")
        print(f"First 500 chars: {result.extracted_text[:500]}")
