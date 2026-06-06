"""
fixer.py — Model-driven SEO fixes.
"""

from __future__ import annotations
import pandas as pd
import subprocess
import os
import csv
import time

# Get the model from env or default to sonnet
MODEL = os.environ.get("RADAR_MODEL", "sonnet")

def call_llm(prompt: str) -> str | None:
    try:
        # It will use the cloud model seamlessly through the Ollama CLI
        result = subprocess.run(
            ["ollama", "run", MODEL, prompt],
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.strip()
    except Exception as e:
        print(f"DEBUG: LLM Call Failed: {e}")
        return None

def fix_titles(df: pd.DataFrame, issues: list[dict]) -> list[dict]:
    """
    Fixes missing and too-short titles using the local LLM.
    Returns a list of {url, old, new}.
    """
    fixes = []

    # Identify URLs needing title fixes
    urls_to_fix = []
    for issue in issues:
        if issue['type'] in ('missing_title', 'title_too_short'):
            urls_to_fix.extend(issue['affected_urls'])

    urls_to_fix = sorted(list(set(urls_to_fix)))

    for url in urls_to_fix:
        # Gather context for the LLM
        row = df[df['Address'] == url].iloc[0]
        old_title = row.get('Title 1', '')
        h1 = row.get('H1-1', 'No H1 found')

        prompt = (
            f"You are an SEO expert. Rewrite this title to be under 60 characters and "
            f"highly relevant to the URL. URL: {url}. Old Title: {old_title}. "
            f"Return ONLY the new title text."
        )

        new_title = call_llm(prompt)
        time.sleep(0.5)

        # Basic validation: retry if too long and we actually got a response
        if new_title and len(new_title) > 60:
            retry_prompt = f"The title '{new_title}' is too long. Please rewrite it to be under 60 characters. Provide ONLY the text."
            new_title = call_llm(retry_prompt)

        fixes.append({
            "url": url,
            "old": old_title if pd.notna(old_title) else "",
            "new": new_title if new_title else "LLM_FIX_FAILED"
        })

    return fixes

def write_fixes_csv(fixes: list[dict], output_path: str):
    """Writes the fixes to a CSV file."""
    if not fixes:
        return

    keys = fixes[0].keys()
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        dict_writer = csv.DictWriter(f, fieldnames=keys)
        dict_writer.writeheader()
        dict_writer.writerows(fixes)
