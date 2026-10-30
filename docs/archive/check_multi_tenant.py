#!/usr/bin/env python3
"""
Multi-Tenant Isolation Audit Script
Checks all API endpoints for practice_id filtering
"""

import re
import os
from pathlib import Path

# List of critical endpoints to check
endpoints = [
    'patients.py',
    'appointments.py',
    'billing.py',
    'reports.py', 
    'imaging.py',
    'insurance.py',
    'treatment.py',
    'labs.py',
    'referrals.py',
    'inventory.py',
    'payments.py',
    'accounting.py',
    'edi.py',
    'staff.py',
]

results = []
issues = []

for endpoint in endpoints:
    filepath = Path(f'coredent-api/app/api/v1/endpoints/{endpoint}')
    if not filepath.exists():
        continue
        
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
        
    # Count select statements
    selects = len(re.findall(r'select\(', content, re.IGNORECASE))
    
    # Count practice_id filters
    practice_filters = len(re.findall(r'practice_id\s*==', content))
    
    # Check if get_current_practice_id is used
    has_practice_dep = 'get_current_practice_id' in content
    
    # Calculate ratio
    if selects > 0:
        ratio = practice_filters / selects
        status = '✅ GOOD' if ratio >= 0.7 else '⚠️  CHECK'
        
        if ratio < 0.7:
            issues.append({
                'file': endpoint,
                'selects': selects,
                'filters': practice_filters,
                'ratio': ratio
            })
    else:
        ratio = 1.0
        status = '✅ GOOD'
    
    results.append({
        'file': endpoint,
        'selects': selects,
        'practice_filters': practice_filters,
        'has_dep': has_practice_dep,
        'ratio': ratio,
        'status': status
    })

# Print results
print('\n' + '=' * 80)
print('MULTI-TENANT ISOLATION AUDIT REPORT')
print('=' * 80)
print(f"\n{'Endpoint':<25} {'Queries':<10} {'Filters':<10} {'Ratio':<10} {'Status'}")
print('-' * 80)

for r in results:
    ratio_str = f"{r['ratio']:.0%}" if r['selects'] > 0 else 'N/A'
    print(f"{r['file']:<25} {r['selects']:<10} {r['practice_filters']:<10} {ratio_str:<10} {r['status']}")

# Summary
total_selects = sum(r['selects'] for r in results)
total_filters = sum(r['practice_filters'] for r in results)
overall_ratio = total_filters / total_selects if total_selects > 0 else 1.0

print('\n' + '=' * 80)
print('SUMMARY')
print('=' * 80)
print(f"Total Endpoints Checked: {len(results)}")
print(f"Total Database Queries: {total_selects}")
print(f"Queries with practice_id Filter: {total_filters}")
print(f"Overall Coverage: {overall_ratio:.0%}")
print()

if overall_ratio >= 0.9:
    print("✅ EXCELLENT: Multi-tenant isolation looks very good!")
elif overall_ratio >= 0.7:
    print("✅ GOOD: Multi-tenant isolation is adequate, but review flagged endpoints")
elif overall_ratio >= 0.5:
    print("⚠️  WARNING: Some endpoints may lack proper isolation")
else:
    print("🚨 CRITICAL: Many endpoints lack proper isolation - REVIEW REQUIRED")

if issues:
    print('\n' + '=' * 80)
    print('ENDPOINTS NEEDING REVIEW')
    print('=' * 80)
    for issue in issues:
        print(f"\n⚠️  {issue['file']}")
        print(f"   Queries: {issue['selects']}, Filtered: {issue['filters']} ({issue['ratio']:.0%})")
        print(f"   Action: Manually review this endpoint for missing practice_id filters")

print('\n' + '=' * 80)
print('NEXT STEPS')
print('=' * 80)
print("1. Review any flagged endpoints manually")
print("2. Check if queries without practice_id are intentional (e.g., lookup tables)")
print("3. Add practice_id filters where needed")
print("4. Run manual penetration tests")
print('=' * 80 + '\n')
