"""Add DemoBanner to all mock data pages"""
import os

pages = {
    'Insurance': 'coredent-style-main/src/pages/Insurance.tsx',
    'Communications': 'coredent-style-main/src/pages/Communications.tsx',
    'Inventory': 'coredent-style-main/src/pages/Inventory.tsx',
    'LabManagement': 'coredent-style-main/src/pages/LabManagement.tsx',
    'Subscriptions': 'coredent-style-main/src/pages/Subscriptions.tsx',
    'ClinicalNotes': 'coredent-style-main/src/pages/ClinicalNotes.tsx',
    'TreatmentPlans': 'coredent-style-main/src/pages/TreatmentPlans.tsx',
    'Reports': 'coredent-style-main/src/pages/Reports.tsx',
    'Settings': 'coredent-style-main/src/pages/Settings.tsx',
    'PublicBooking': 'coredent-style-main/src/pages/PublicBooking.tsx',
    'DentalChart': 'coredent-style-main/src/pages/DentalChart.tsx',
}

for name, path in pages.items():
    try:
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        if 'DemoBanner' in content:
            print(f'[SKIP] {name} - already has DemoBanner')
            continue
        
        # Add import at top
        content = content.replace(
            "from 'react';",
            "from 'react';\nimport { DemoBanner } from '@/components/DemoBanner';"
        )
        content = content.replace(
            "from 'react';\n",
            "from 'react';\nimport { DemoBanner } from '@/components/DemoBanner';\n"
        )
        
        # Add <DemoBanner /> after <div className="p-6
        content = content.replace(
            '<div className="p-6',
            '<DemoBanner />\n      <div className="p-6'
        )
        content = content.replace(
            "<div className='p-6",
            "<DemoBanner />\n      <div className='p-6"
        )
        
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f'[DONE] {name} - DemoBanner added')
    except FileNotFoundError:
        print(f'[MISS] {name} - file not found: {path}')
    except Exception as e:
        print(f'[ERR] {name} - {e}')

print("\nAll pages processed!")