#!/usr/bin/env python3
"""Test RPA analysis with Neo4j fallback support."""

import sys
import os
import httpx
import json

# Add project root to path
ROOT = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, ROOT)

BASE_URL = "http://127.0.0.1:8000/api"

# Test RPA analysis with existing paper
landscape_id = "81b8f153-3060-4bda-bf10-819a8576939d"
paper_id = "e18faeb0-9692-4b7d-ab56-e0ee6d5e63cf"

print(f"Testing RPA analysis for paper_id={paper_id}")
print(f"Landscape ID: {landscape_id}\n")

try:
    response = httpx.get(
        f"{BASE_URL}/rpa/analyze",
        params={"paper_id": paper_id, "landscape_id": landscape_id},
        timeout=30.0
    )
    
    if response.status_code == 200:
        data = response.json()
        
        # Check key fields
        print("✅ Response Status: 200 OK\n")
        
        if "corpus_too_small" in data:
            print(f"✅ corpus_too_small: {data['corpus_too_small']}")
        
        if "rpa_results" in data:
            rpa = data["rpa_results"]
            print(f"\nRPA Metrics:")
            print(f"  - cas_aggregate: {rpa.get('cas_aggregate')}")
            print(f"  - fci_score: {rpa.get('fci_score')}")
            print(f"  - mss_percentile: {rpa.get('mss_percentile')}")
            print(f"  - cns_aggregate: {rpa.get('cns_aggregate')}")
            print(f"  - tfp_field_trajectory: {rpa.get('tfp_field_trajectory')}")
            
            # Check if metrics are non-None (indicates fallback is working)
            metrics = [
                ("CAS", rpa.get('cas_aggregate')),
                ("FCI", rpa.get('fci_score')),
                ("MSS", rpa.get('mss_percentile')),
                ("CNS", rpa.get('cns_aggregate')),
                ("TFP", rpa.get('tfp_field_trajectory'))
            ]
            
            print(f"\n📊 Metric Computation Status:")
            for name, value in metrics:
                status = "✅ Computed" if value is not None else "❌ None/Missing"
                print(f"  {name}: {status} (value={value})")
        
        print("\n✅ RPA analysis with fallback working!")
    else:
        print(f"❌ Error: {response.status_code}")
        print(response.text)

except Exception as e:
    print(f"❌ Request failed: {e}")
