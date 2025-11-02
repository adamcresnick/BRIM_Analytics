#!/usr/bin/env python3
"""
Test AWS Textract on TIFF files from patient binary data
Tests extraction from the radiation therapy TIFF document identified in investigation
"""

import boto3
import logging
import io
import json
import base64
from PIL import Image
from botocore.exceptions import ClientError

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_textract_on_tiff():
    """
    Test AWS Textract on a known TIFF file from patient data

    Target file: Binary/ez99FproUH0nx9RO4d0Dxn0nrc9rzkbd_apMU2ZLJ6H03
    - Patient: eQSB0y3q.OmvN40Yhg9.eCBk5-9c-Qp-FT3pBWoSGuL83
    - DocumentReference: et.iSybe2pXj6PQe3t6Z0AVnS86AHXFYtuJ0vkFCrUnY3
    - Content type: image/tiff
    - Size: 58.7KB
    - Context: Radiation therapy document from 2018-04-25
    """

    # Initialize AWS session with radiant-prod profile
    session = boto3.Session(profile_name='radiant-prod', region_name='us-east-1')

    # Initialize AWS clients
    s3_client = session.client('s3')
    textract_client = session.client('textract')

    # S3 bucket and key
    bucket = 'radiant-prd-343218191717-us-east-1-prd-ehr-pipeline'
    key = 'prd/source/Binary/ez99FproUH0nx9RO4d0Dxn0nrc9rzkbd_apMU2ZLJ6H03'

    logger.info(f"Testing AWS Textract on TIFF file")
    logger.info(f"  Bucket: {bucket}")
    logger.info(f"  Key: {key}")
    logger.info(f"  Expected content: Radiation therapy documentation")

    try:
        # Step 1: Verify file exists in S3
        logger.info("\n[Step 1] Verifying file exists in S3...")
        response = s3_client.head_object(Bucket=bucket, Key=key)
        file_size = response['ContentLength']
        content_type = response.get('ContentType', 'unknown')
        logger.info(f"  ✅ File found: {file_size:,} bytes, type: {content_type}")

        # Step 2: Download FHIR Binary resource
        logger.info("\n[Step 2] Downloading FHIR Binary resource from S3...")
        obj = s3_client.get_object(Bucket=bucket, Key=key)
        binary_json = json.loads(obj['Body'].read())
        logger.info(f"  ✅ Downloaded FHIR Binary resource")
        logger.info(f"  Resource type: {binary_json.get('resourceType')}")
        logger.info(f"  Content type: {binary_json.get('contentType')}")

        # Step 2.5: Decode base64 TIFF data
        logger.info("\n[Step 2.5] Decoding base64 TIFF data...")
        base64_data = binary_json.get('data', '')
        tiff_bytes = base64.b64decode(base64_data)
        logger.info(f"  ✅ Decoded {len(tiff_bytes):,} bytes of TIFF data")

        # Step 2.75: Convert TIFF to PNG for Textract
        logger.info("\n[Step 2.75] Converting TIFF to PNG for Textract...")
        # Open TIFF with PIL
        tiff_image = Image.open(io.BytesIO(tiff_bytes))
        logger.info(f"  TIFF info: {tiff_image.size} pixels, mode: {tiff_image.mode}")

        # Convert to PNG in memory
        png_buffer = io.BytesIO()
        tiff_image.save(png_buffer, format='PNG')
        png_bytes = png_buffer.getvalue()
        logger.info(f"  ✅ Converted to PNG: {len(png_bytes):,} bytes")

        # Step 3: Call Textract to detect document text
        logger.info("\n[Step 3] Calling AWS Textract detect_document_text...")
        textract_response = textract_client.detect_document_text(
            Document={
                'Bytes': png_bytes
            }
        )

        # Step 4: Extract text from response
        logger.info("\n[Step 4] Extracting text from Textract response...")
        blocks = textract_response.get('Blocks', [])
        logger.info(f"  Total blocks detected: {len(blocks)}")

        # Extract LINE blocks (contains actual text lines)
        lines = []
        words = []
        for block in blocks:
            if block['BlockType'] == 'LINE':
                lines.append(block.get('Text', ''))
            elif block['BlockType'] == 'WORD':
                words.append(block.get('Text', ''))

        logger.info(f"  Lines extracted: {len(lines)}")
        logger.info(f"  Words extracted: {len(words)}")

        # Combine into full text
        full_text = '\n'.join(lines)
        logger.info(f"  Total text length: {len(full_text)} characters")

        # Step 5: Display results
        logger.info("\n" + "="*80)
        logger.info("TEXTRACT EXTRACTION RESULTS")
        logger.info("="*80)

        if full_text:
            logger.info("\n[First 2000 characters of extracted text]:")
            logger.info("-"*80)
            print(full_text[:2000])
            logger.info("-"*80)

            logger.info("\n[Last 500 characters of extracted text]:")
            logger.info("-"*80)
            print(full_text[-500:])
            logger.info("-"*80)

            # Check for radiation-specific keywords
            radiation_keywords = [
                'radiation', 'dose', 'gy', 'gray', 'therapy', 'treatment',
                'rt', 'focal', 'boost', 'cgy', 'field', 'port', 'plan'
            ]

            found_keywords = []
            for keyword in radiation_keywords:
                if keyword in full_text.lower():
                    found_keywords.append(keyword)

            logger.info(f"\n[Radiation keywords found]: {found_keywords}")

            # Step 6: Save to file
            output_file = 'output/textract_test_radiation_tiff.txt'
            with open(output_file, 'w') as f:
                f.write(full_text)
            logger.info(f"\n✅ Full extracted text saved to: {output_file}")

            return {
                'success': True,
                'text_length': len(full_text),
                'lines': len(lines),
                'words': len(words),
                'keywords_found': found_keywords,
                'output_file': output_file
            }
        else:
            logger.warning("⚠️  No text extracted from TIFF file")
            return {
                'success': False,
                'error': 'No text extracted'
            }

    except ClientError as e:
        error_code = e.response['Error']['Code']
        error_message = e.response['Error']['Message']
        logger.error(f"❌ AWS Error: {error_code} - {error_message}")
        return {
            'success': False,
            'error': f"{error_code}: {error_message}"
        }
    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}", exc_info=True)
        return {
            'success': False,
            'error': str(e)
        }


if __name__ == '__main__':
    logger.info("="*80)
    logger.info("AWS TEXTRACT TIFF EXTRACTION TEST")
    logger.info("="*80)

    result = test_textract_on_tiff()

    logger.info("\n" + "="*80)
    logger.info("TEST SUMMARY")
    logger.info("="*80)

    if result.get('success'):
        logger.info("✅ Textract extraction SUCCESSFUL")
        logger.info(f"   Extracted {result['text_length']:,} characters")
        logger.info(f"   Found {len(result['keywords_found'])} radiation keywords")
        logger.info(f"   Output: {result['output_file']}")
    else:
        logger.error(f"❌ Textract extraction FAILED: {result.get('error')}")
