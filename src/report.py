"""
Report Generator Module.

Formats the evaluated and scored hackathons into a structured, highly professional
Markdown intelligence report (.md file), saved locally for delivery.
"""

import datetime
import logging
import os

log = logging.getLogger(__name__)


def generate_report(scored_events: list[dict], github_intel: dict) -> str:
    """
    Generate a detailed Markdown intelligence report for the scored events.

    Args:
        scored_events: List of scored hackathon dicts.
        github_intel: Dictionary containing GitHub intelligence for each hackathon by title.

    Returns:
        The absolute file path of the generated markdown report.
    """
    log.info(f"Generating markdown report for {len(scored_events)} events...")

    date_str = datetime.date.today().strftime("%Y-%m-%d")
    
    # Ensure reports directory exists in the workspace
    reports_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "reports"))
    os.makedirs(reports_dir, exist_ok=True)
    
    report_filename = f"report_{date_str}.md"
    report_path = os.path.join(reports_dir, report_filename)

    lines = []
    lines.append(f"# Hackathon Intelligence Digest — {date_str}")
    lines.append(f"Generated on {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} (IST)\n")
    lines.append("This digest contains evaluated hackathon opportunities with high Founder Opportunity Scores (FOS) or excellent Easy-Win potential, enriched with GitHub community intelligence.\n")

    # Table of contents / executive summary
    lines.append("## Executive Summary\n")
    lines.append("| Event Title | Source | FOS Score | Easy-Win Score | Verdict | Recommendation |")
    lines.append("|-------------|--------|-----------|----------------|---------|----------------|")
    for event in scored_events:
        title = event.get("title", "Unknown")
        source = event.get("source", "unknown").upper()
        fos = event.get("fos_score", 0.0)
        easy_win = event.get("easy_winning_potential", 0.0)
        verdict = event.get("fos_verdict", "⚠️")
        rec = event.get("recommendation", "APPLY")
        lines.append(f"| {title} | {source} | **{fos:.1f}/10** | **{easy_win:.1f}/10** | {verdict} | `{rec}` |")
    lines.append("\n---\n")

    # Detailed Event Profiles
    lines.append("## Detailed Event Profiles\n")

    for i, event in enumerate(scored_events, start=1):
        title = event.get("title", "Unknown")
        verdict = event.get("fos_verdict", "⚠️")
        fos = event.get("fos_score", 0.0)
        easy_win = event.get("easy_winning_potential", 0.0)
        source = event.get("source", "unknown").upper()
        
        lines.append(f"### {i}. {title} ({verdict})")
        lines.append(f"- **Source**: {source}")
        lines.append(f"- **Founder Opportunity Score (FOS)**: **{fos:.1f}/10**")
        lines.append(f"- **Easy-Win Potential**: **{easy_win:.1f}/10**")
        lines.append(f"- **Dates**: {event.get('dates', 'N/A')}")
        lines.append(f"- **Registration Deadline**: {event.get('registration_deadline', 'N/A')}")
        lines.append(f"- **Mode / Location**: {event.get('mode', 'N/A').upper()}")
        lines.append(f"- **Team Size**: {event.get('team_size', 'N/A')}")
        if event.get("link"):
            lines.append(f"- **URL**: [Register Here]({event.get('link')})")
        lines.append("")

        # Personal Pitch
        lines.append(f"> **Why this matters**: {event.get('why_relevant', '')}\n")

        # FOS Score breakdown
        lines.append("#### Opportunity Scores")
        lines.append(f"- **Sponsor Quality (30% weight)**: {event.get('sponsor_quality', 0.0)}/10")
        lines.append(f"- **Hiring Potential (25% weight)**: {event.get('hiring_potential', 0.0)}/10")
        lines.append(f"- **Startup Potential (20% weight)**: {event.get('startup_potential', 0.0)}/10")
        lines.append(f"- **Prize Pool Score (15% weight)**: {event.get('prize_score', 0.0)}/10")
        lines.append(f"- **Networking Potential (10% weight)**: {event.get('networking_potential', 0.0)}/10")
        lines.append("")

        # Easy Win Analysis
        lines.append("#### Win Probability & Easy-Win Analysis")
        lines.append(f"> [!TIP]")
        lines.append(f"> **Win Score**: {easy_win:.1f}/10")
        lines.append(f"> {event.get('easy_winning_analysis', 'No additional win probability details provided.')}")
        lines.append("")

        # Sponsors & Prizes
        lines.append("#### Prizes & Sponsors")
        lines.append(f"- **Total Prize Pool**: {event.get('prize_pool', 'N/A')}")
        if event.get("prize_breakdown"):
            lines.append(f"- **Prize Breakdown**: {event.get('prize_breakdown')}")
        lines.append(f"- **Sponsor Analysis**: {event.get('sponsor_analysis', 'N/A')}")
        lines.append("")

        # GitHub Intelligence
        git = github_intel.get(title, {})
        lines.append("#### GitHub Intelligence & Open Source Ecosystem")
        if git:
            lines.append(f"- **Total Star Count**: {git.get('total_stars', 0)}")
            lines.append(f"- **Good First Issues Found**: {git.get('good_first_issues', 0)}")
            lines.append(f"- **Open Bounty Issues**: {git.get('bounty_count', 0)}")
            
            # Related Repos
            repos = git.get("repos", [])
            if repos:
                lines.append("- **Relevant Codebases**:")
                for r in repos[:3]:
                    lines.append(f"  - [{r['name']}]({r['url']}) (⭐ {r['stars']}) - {r['description'][:150]}")
            else:
                lines.append("- No immediate related repositories found on GitHub.")
                
            # Related sponsor orgs
            sorgs = git.get("sponsors_intel", {})
            if sorgs:
                lines.append("- **Sponsor Orgs discovered**:")
                for name, info in sorgs.items():
                    lines.append(f"  - **{name}**: [{info['org_name']}]({info['github_url']}) ({info['public_repos']} public repos, {info['followers']} followers)")
        else:
            lines.append("- GitHub intelligence scan failed or skipped.")
        lines.append("")

        # Core Analysis
        lines.append("#### Core Strategic Analysis")
        lines.append(f"- **Competition & Participant Strategy**: {event.get('competition_analysis', 'N/A')}")
        lines.append(f"- **Networking Upside**: {event.get('networking_analysis', 'N/A')}")
        lines.append(f"- **Career Upside & Hiring Tracks**: {event.get('career_upside', 'N/A')}")
        lines.append(f"- **ROI Analysis**: {event.get('roi_analysis', 'N/A')}")
        lines.append("")

        # Best project categories
        cats = event.get("best_categories", [])
        if cats:
            lines.append("#### Suggested Ideas to Build")
            for cat in cats:
                lines.append(f"- `{cat}`")
            lines.append("")

        lines.append("---\n")

    # Write report content to file
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    log.info(f"Report successfully saved to {report_path}")
    return report_path
