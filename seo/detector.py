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

    Implements all rules from rulebook.md using pandas.
    """
    issues = []

    def add(t, sev, urls, explanation):
        urls = sorted(list(set(urls)))
        if urls:
            issues.append({"type": t, "severity": sev, "affected_urls": urls,
                           "count": len(urls), "explanation": explanation})

    # --- Pre-processing / Helpers ---
    # Ensure numeric columns are actually numeric
    numeric_cols = [
        'Status Code', 'Title 1 Length', 'Title 1 Pixel Width',
        'Inlinks', 'Response Time', 'Word Count', 'Meta Description 1 Length'
    ]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')

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
    # We only consider non-empty titles for duplication
    titles_df = df[is_html & is_indexable].copy()
    titles_df = titles_df[titles_df['Title 1'].notna() & (titles_df['Title 1'].str.strip() != '')]
    dup_title_mask = titles_df['Title 1'].duplicated(keep=False)
    add("duplicate_title", "High", titles_df[dup_title_mask]['Address'].tolist(), "Pages sharing an identical title.")

    # title_too_long: Pixel Width > 561 OR Length > 60
    too_long_mask = (df_idx200['Title 1 Pixel Width'] > 561) | (df_idx200['Title 1 Length'] > 60)
    add("title_too_long", "Medium", df_idx200[too_long_mask]['Address'].tolist(), "Titles likely truncated in search results.")

    # title_too_short: Title 1 Length < 30 (and not empty)
    too_short_mask = (df_idx200['Title 1 Length'] < 30) & (df_idx200['Title 1 Length'].notna())
    add("title_too_short", "Low", df_idx200[too_short_mask]['Address'].tolist(), "Titles that are too short for optimal SEO.")

    # --- Meta Descriptions ---
    # missing_meta_description: Meta Description 1 empty, indexable 200 page
    missing_meta_urls = df_idx200[df_idx200['Meta Description 1'].isna() | (df_idx200['Meta Description 1'].str.strip() == '')]['Address'].tolist()
    add("missing_meta_description", "Medium", missing_meta_urls, "Indexable pages missing a meta description.")

    # duplicate_meta_description: same meta on 2+ indexable URLs (ignore empty)
    meta_df = df[is_html & is_indexable].copy()
    meta_df = meta_df[meta_df['Meta Description 1'].notna() & (meta_df['Meta Description 1'].str.strip() != '')]
    dup_meta_mask = meta_df['Meta Description 1'].duplicated(keep=False)
    add("duplicate_meta_description", "Medium", meta_df[dup_meta_mask]['Address'].tolist(), "Pages sharing an identical meta description.")

    # meta_description_too_long: Meta Description 1 Length > 155
    too_long_meta_mask = (df_idx200['Meta Description 1 Length'] > 155)
    add("meta_description_too_long", "Low", df_idx200[too_long_meta_mask]['Address'].tolist(), "Meta descriptions likely truncated in search results.")

    # --- H1 ---
    # missing_h1: H1-1 empty on a 200 page
    missing_h1_urls = df[is_200 & (df['H1-1'].isna() | (df['H1-1'].str.strip() == ''))]['Address'].tolist()
    add("missing_h1", "Medium", missing_h1_urls, "200 pages missing an H1 tag.")

    # duplicate_h1: same H1-1 on 2+ indexable URLs
    h1_df = df[is_html & is_indexable].copy()
    h1_df = h1_df[h1_df['H1-1'].notna() & (h1_df['H1-1'].str.strip() != '')]
    dup_h1_mask = h1_df['H1-1'].duplicated(keep=False)
    add("duplicate_h1", "Low", h1_df[dup_h1_mask]['Address'].tolist(), "Pages sharing an identical H1 header.")

    # --- Response codes & Redirects ---
    # broken_link: Status Code in 400–499
    broken_links = df[(df['Status Code'] >= 400) & (df['Status Code'] <= 499)]['Address'].tolist()
    add("broken_link", "High", broken_links, "URLs returning a client error (4xx).")

    # server_error: Status Code in 500–599
    server_errors = df[(df['Status Code'] >= 500) & (df['Status Code'] <= 599)]['Address'].tolist()
    add("server_error", "High", server_errors, "URLs returning a server error (5xx).")

    # redirect: Status Code in 300–399
    is_redirect = (df['Status Code'] >= 300) & (df['Status Code'] <= 399)
    redirects = df[is_redirect]['Address'].tolist()
    add("redirect", "Medium", redirects, "URLs that redirect (3xx).")

    # redirect_chain: a redirect whose Redirect URL is itself a redirecting URL
    # Map of {Address: Redirect URL}
    redirect_map = df[is_redirect].set_index('Address')['Redirect URL'].to_dict()
    # A chain exists if the target (Redirect URL) is also a source (Address) of another redirect
    redirecting_addresses = set(redirect_map.keys())
    chain_urls = [addr for addr, target in redirect_map.items() if target in redirecting_addresses]
    add("redirect_chain", "High", chain_urls, "Redirects that point to another redirect (chains).")

    # --- Content & Indexability ---
    # thin_content: Word Count < 200 on an indexable page
    thin_urls = df[is_indexable & (df['Word Count'] < 200)]['Address'].tolist()
    add("thin_content", "Low", thin_urls, "Indexable pages with very low word count (< 200).")

    # non_indexable_but_linked: Indexability == 'Non-Indexable' AND Inlinks > 0
    non_idx_linked = df[(df['Indexability'].str.strip().str.lower() == 'non-indexable') & (df['Inlinks'] > 0)]['Address'].tolist()
    add("non_indexable_but_linked", "Medium", non_idx_linked, "Pages marked Non-Indexable but still receiving internal links.")

    # orphan_page: Inlinks = 0 on an indexable 200 page
    orphan_urls = df_idx200[df_idx200['Inlinks'] == 0]['Address'].tolist()
    add("orphan_page", "Medium", orphan_urls, "Indexable pages with zero internal links in.")

    # --- Performance ---
    # slow_page: Response Time > 1.0
    slow_urls = df[df['Response Time'] > 1.0]['Address'].tolist()
    add("slow_page", "Low", slow_urls, "Pages with a response time greater than 1 second.")

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
