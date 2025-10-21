#!/usr/bin/env python3
"""
Simple standalone test for MedGemma agent
"""
import sys
sys.path.append('/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/mvp')

from agents.medgemma_agent import MedGemmaAgent
import time

print("Initializing MedGemma agent...")
medgemma = MedGemmaAgent(model_name="gemma2:27b")

print("Testing simple extraction...")
simple_prompt = """
Extract the following information from this radiology report in JSON format:

Report: "MRI brain shows stable post-operative changes. No new enhancing lesions."

Extract:
{
  "imaging_type": "MRI Brain",
  "tumor_status": "Stable"
}
"""

print("Sending extraction request...")
start = time.time()
result = medgemma.extract(simple_prompt)
elapsed = time.time() - start

print(f"\n✅ Extraction completed in {elapsed:.1f} seconds")
print(f"Success: {result.success}")
print(f"Data: {result.extracted_data}")
print(f"Confidence: {result.confidence}")
if result.error:
    print(f"Error: {result.error}")
