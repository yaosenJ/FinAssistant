# -*- coding: utf-8 -*-
"""Generate all 49 stock reports and investment summary"""
import json, os, sys, traceback

os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, '.')

from report_generator import save_all_reports, save_summary_report

# Load data
with open('output/score_results.json', 'r', encoding='utf-8') as f:
    results = json.load(f)
with open('output/Portfolio.json', 'r', encoding='utf-8') as f:
    portfolio = json.load(f)

print(f'Loaded {len(results)} stocks, portfolio has {len(portfolio)} entries')

# Step 1: Generate all 49 stock reports with charts
try:
    save_all_reports(results, 'output/个股投资研报')
    print('All stock reports generated!')
except Exception as e:
    traceback.print_exc()
    print(f'Error generating stock reports: {e}')

# Verify
report_dir = 'output/个股投资研报'
md_files = [f for f in os.listdir(report_dir) if f.endswith('.md')]
print(f'Total .md reports: {len(md_files)}')

charts_dir = os.path.join(report_dir, 'charts')
if os.path.exists(charts_dir):
    png_files = [f for f in os.listdir(charts_dir) if f.endswith('.png')]
    print(f'Total .png charts: {len(png_files)}')

# Step 2: Generate investment summary report
try:
    save_summary_report(portfolio, results, '投资报告.md')
    print('Investment summary report generated!')
except Exception as e:
    traceback.print_exc()
    print(f'Error generating summary report: {e}')

print('DONE')
