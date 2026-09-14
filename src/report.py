"""
Report Generator Module (v4).

Formats evaluated events into a structured, comprehensive
Markdown intelligence report (.md file), supporting:
- Dual scoring frameworks (Founder FOS vs Student SOS)
- Personalized relevance explanations
- GitHub ecosystem intelligence
"""

import datetime
import logging
import os

log = logging.getLogger(__name__)


def generate_report(scored_events: list[dict], github_intel: dict) -> str:
    """
    Generate a detailed Markdown intelligence report for evaluated events.
    """
    log.info(f"Generating markdown report for {len(scored_events)} events...")

    date_str = datetime.date.today().strftime("%Y-%m-%d")
    reports_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "reports"))
    os.makedirs(reports_dir, exist_ok=True)

    report_filename = f"report_{date_str}.md"
    report_path = os.path.join(reports_dir, report_filename)

    lines = []
    lines.append(f"# Opportunity Intelligence Digest — {date_str}")
    lines.append(f"Generated on {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} (IST)\n")
    lines.append("Evaluated using multi-stage intelligence: Founder Opportunity Score (FOS) for global platforms, Student Opportunity Score (SOS) for college portals, and personalized relevance matching.\n")

    # Executive Summary Table
    lines.append("## Executive Summary\n")
    lines.append("| Event Title | Type | Source | Opp Score | Win Prob | Match % | Verdict | Recommendation |")
    lines.append("|-------------|------|--------|-----------|----------|---------|---------|----------------|")
    for event in scored_events:
        title = event.get("title", "Unknown")
        etype = event.get("event_type", "hackathon").upper()
        source = event.get("source", "unknown").upper()
        source_type = event.get("source_type", "global_platform")
        score = event.get("sos_score") if source_type == "college_portal" else event.get("fos_score", 0.0)
        score = score or 0.0
        easy_win = event.get("easy_winning_potential", 0.0)
        rel_score = event.get("relevance_score", 5.0)
        verdict = event.get("sos_verdict") if source_type == "college_portal" else event.get("fos_verdict", "⚠️")
        verdict = verdict or "⚠️"
        rec = event.get("recommendation", "APPLY")
        match_pct = int(min(100, max(10, rel_score * 10)))
        lines.append(f"| {title} | {etype} | {source} | **{score:.1f}/10** | **{easy_win:.1f}/10** | {match_pct}% | {verdict} | `{rec}` |")
    lines.append("\n---\n")

    # Detailed Event Profiles
    lines.append("## Detailed Event Profiles\n")

    for i, event in enumerate(scored_events, start=1):
        title = event.get("title", "Unknown")
        etype = event.get("event_type", "hackathon").upper()
        source = event.get("source", "unknown").upper()
        source_type = event.get("source_type", "global_platform")
        is_college = source_type == "college_portal"
        opp_score = (event.get("sos_score") if is_college else event.get("fos_score")) or 0.0
        score_label = "Student Opportunity Score (SOS)" if is_college else "Founder Opportunity Score (FOS)"
        verdict = (event.get("sos_verdict") if is_college else event.get("fos_verdict")) or "⚠️"
        easy_win = event.get("easy_winning_potential", 0.0)

        lines.append(f"### {i}. {title} ({verdict})")
        lines.append(f"- **Type**: `{etype}`")
        lines.append(f"- **Source**: {source} ({source_type})")
        lines.append(f"- **{score_label}**: **{opp_score:.1f}/10**")
        lines.append(f"- **Easy-Win Potential**: **{easy_win:.1f}/10**")
        lines.append(f"- **Dates**: {event.get('dates', 'N/A')}")
        lines.append(f"- **Registration Deadline**: {event.get('registration_deadline', 'N/A')}")
        lines.append(f"- **Mode / Location**: {str(event.get('mode', 'N/A')).upper()}")
        lines.append(f"- **Team Size**: {event.get('team_size', 'N/A')}")
        if event.get("link"):
            lines.append(f"- **Registration Link**: [{title}]({event.get('link')})")
        else:
            lines.append(f"- **Registration Link**: *Direct link unavailable — search on {source}*")
        lines.append("")

        # Personal relevance & pitch
        rel_exp = event.get("relevance_explanation")
        why = event.get("why_relevant")
        if rel_exp:
            lines.append(f"> **Why this matches you**: {rel_exp}\n")
        elif why:
            lines.append(f"> **Why this matters**: {why}\n")

        # Opportunity Score Breakdown
        lines.append(f"#### {score_label} Breakdown")
        if is_college:
            lines.append(f"- **Learning Value (30%)**: {event.get('learning_value', 5.0)}/10")
            lines.append(f"- **Skill Building (25%)**: {event.get('skill_building', 5.0)}/10")
            lines.append(f"- **Network Value (20%)**: {event.get('network_value', 5.0)}/10")
            lines.append(f"- **Competitive Achievement (15%)**: {event.get('competitive_achievement', 5.0)}/10")
            lines.append(f"- **Career Relevance (10%)**: {event.get('career_relevance', 5.0)}/10")
        else:
            lines.append(f"- **Sponsor Quality (30%)**: {event.get('sponsor_quality', 5.0)}/10")
            lines.append(f"- **Hiring Potential (25%)**: {event.get('hiring_potential', 5.0)}/10")
            lines.append(f"- **Startup Potential (20%)**: {event.get('startup_potential', 5.0)}/10")
            lines.append(f"- **Prize Pool (15%)**: {event.get('prize_score', 5.0)}/10")
            lines.append(f"- **Networking Potential (10%)**: {event.get('networking_potential', 5.0)}/10")
        lines.append("")

        # Win Probability
        lines.append("#### Win Probability & Easy-Win Analysis")
        lines.append(f"> **Win Score**: {easy_win:.1f}/10")
        lines.append(f"> {event.get('easy_winning_analysis', 'Standard competition profile.')}\n")

        # Prizes & Sponsors
        lines.append("#### Prizes & Organizers")
        lines.append(f"- **Prize Pool**: {event.get('prize_pool', 'N/A')}")
        if event.get("prize_breakdown"):
            lines.append(f"- **Prize Breakdown**: {event.get('prize_breakdown')}")
        if event.get("sponsors"):
            lines.append(f"- **Sponsors/Partners**: {', '.join(event.get('sponsors', []))}")
        lines.append(f"- **Sponsor Analysis**: {event.get('sponsor_analysis', 'N/A')}\n")

        # GitHub Intelligence (for global/community events)
        git = github_intel.get(title, {})
        if git and (git.get("repos") or git.get("total_stars") or git.get("sponsors_intel")):
            lines.append("#### GitHub Intelligence & Open Source Ecosystem")
            lines.append(f"- **Total Star Count**: {git.get('total_stars', 0)}")
            lines.append(f"- **Good First Issues**: {git.get('good_first_issues', 0)}")
            lines.append(f"- **Open Bounty Issues**: {git.get('bounty_count', 0)}")
            repos = git.get("repos", [])
            if repos:
                lines.append("- **Relevant Codebases**:")
                for r in repos[:3]:
                    lines.append(f"  - [{r['name']}]({r['url']}) (⭐ {r['stars']}) - {r.get('description', '')[:120]}")
            lines.append("")

        # Suggested Categories
        cats = event.get("best_categories", [])
        if cats:
            lines.append("#### Recommended Tracks & Ideas")
            for cat in cats:
                lines.append(f"- `{cat}`")
            lines.append("")

        lines.append("---\n")

    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    log.info(f"Report successfully saved to {report_path}")
    return report_path
