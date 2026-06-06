"""
detector.py — deterministic SEO issue detection from a Screaming Frog internal_all.csv.

This implementation uses pandas for efficient data manipulation and detection logic
as per the rulebook.
"""

from __future__ import annotations
import pandas as pd
import os
from collections import defaultdict

def load_rows(export_dir: str) -> pd.DataFrame:
    path = os.path.join(export_dir, "internal_all.csv")
    # Screaming Frog CSVs can have encoding issues or BOM; utf-8-sig handles it.
    return pd.read_csv(path, encoding="utf-8-sig")

def detect(df: pd.DataFrame) -> list[dict]:
    """Return a list of issue dicts: {type, severity, affected_urls, count, explanation}.

    Implements rules from rulebook.md using pandas.
    """
    issues = []

    def add(t, sev, urls, explanation):
        urls = sorted(list(set(urls)))
        if urls:
            issues.append({"type": t, "severity": sev, "affected_urls": urls,
                           "count": len(urls), "explanation": explanation})

    # --- Pre-processing / Helpers ---
    # Ensure numeric columns are actually numeric
    df['Status Code'] = pd.to_numeric(df['Status Code'], errors='coerce')
    df['Title 1 Length'] = pd.to_numeric(df['Title 1 Length'], errors='coerce')
    df['Title 1 Pixel Width'] = pd.to_numeric(df['Title 1 Pixel Width'], errors='coerce')
    df['Inlinks'] = pd.to_numeric(df['Inlinks'], errors='coerce')
    df['Response Time'] = pd.to_numeric(df['Response Time'], errors='coerce')

    # Pre-filters
    is_html = df['Content Type'].str.contains('text/html', case=False, na=False)
    is_200 = df['Status Code'] == 200
    is_indexable = df['Indexability'].str.strip().str.lower() == 'indexable'

    # The core set for title/meta/H1 checks: HTML, 200, and Indexable
    df_idx200 = df[is_html & is_200 & is_indexable]

    # --- Titles ---
    # missing_title: Title 1 empty, indexable 200 page
    missing_title_urls = df_idx200[df_idx200['Title 1'].isna() | (df_idx200['Title 1'].str.strip() == '')]['Address'].tolist()
    add("missing_title", "High", missing_title_urls, "Indexable pages with no title tag.")

    # duplicate_title: same Title 1 on 2+ indexable URLs
    # Rule: Indexability == 'Indexable', ignore empty/non-HTML
    titles_df = df[is_html & is_indexable].copy()
    titles_df = titles_df[titles_df['Title 1'].notna() & (titles_df['Title 1'].str.strip() != '')]
    dup_title_mask = titles_df['Title 1'].duplicated(keep=False)
    add("duplicate_title", "High", titles_df[dup_title_mask]['Address'].tolist(), "Pages sharing an identical title.")

    # title_too_long: Pixel Width > 561 OR Length > 60
    too_long_mask = (df_idx200['Title 1 Pixel Width'] > 561) | (df_idx200['Title 1 Length'] > 60)
    add("title_too_long", "Medium", df_idx200[too_long_mask]['Address'].tolist(), "Titles likely truncated in search results.")

    # --- H1 ---
    # missing_h1: H1-1 empty on a 200 page
    missing_h1_urls = df[is_200 & (df['H1-1'].isna() | (df['H1-1'].str.strip() == ''))]['Address'].tolist()
    add("missing_h1", "Medium", missing_h1_urls, "200 pages missing an H1 tag.")

    # --- Response codes ---
    # broken_link: Status Code in 400–499
    broken_links = df[(df['Status Code'] >= 400) & (df['Status Code'] <= 499)]['Address'].tolist()
    add("broken_link", "High", broken_links, "URLs returning a client error (4xx).")

    # server_error: Status Code in 500–599
    server_errors = df[(df['Status Code'] >= 500) & (df['Status Code'] <= 599)]['Address'].tolist()
    add("server_error", "High", server_errors, "URLs returning a server error (5xx).")

    # redirect: Status Code in 300–399
    redirects = df[(df['Status Code'] >= 300) & (df['Status Code'] <= 399)]['Address'].tolist()
    add("redirect", "Medium", redirects, "URLs that redirect (3xx).")

    # --- Orphan pages ---
    # orphan_page: Inlinks = 0 on an indexable 200 page
    orphan_urls = df_idx200[df_idx200['Inlinks'] == 0]['Address'].tolist()
    add("orphan_page", "Medium", orphan_urls, "Indexable pages with zero internal links in.")

    return issues


def summarize(issues: list[dict]) -> dict:
    by_sev = defaultdict(int)
    for i in issues:
        by_sev[i["severity"]] += 1
    return {"total_issues": len(issues),
            "by_severity": {"High": by_sev["High"], "Medium": by_sev["Medium"], "Low": by_sev["Low"]}}


if __name__ == "__main__":
    import sys, json
    d = sys.argv[1] if len(sys.argv) > 1 else "../sample-export"
    df = load_rows(d)
    iss = detect(df)
    print(f"Loaded {len(df)} rows, detected {len(iss)} issue types.")
    print(json.dumps(summarize(iss), indent=2))
    for i in iss:
        print(f"  [{i['severity']:<6}] {i['type']:<24} x{i['count']}")
