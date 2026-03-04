"""Scraper: e-Grantz — Kerala SC/ST/OBC scholarship data.

Strategy
--------
e-Grantz (https://egrantz.kerala.gov.in) is login-protected for applications,
but the scholarship NAMES, eligibility criteria, and amounts are publicly
documented on informational pages and gov circulars.

We scrape the publicly visible scheme listing from known Kerala govt
information pages. This gives us the hyper-local SC/ST data that
myScheme misses.

Legal: Only publicly visible pages, no login bypass.
"""

from __future__ import annotations

from datetime import datetime

from data.models import Scholarship

# ── Curated Kerala SC/ST/OBC scholarship data ─────────────────
#
# e-Grantz itself doesn't expose a scrapable listing page without login.
# Instead, we maintain a curated dataset sourced from official government
# notifications, Buddy4Study, and other public information sources.
#
# This is the "one script to maintain" approach — when new schemes are
# announced, we add them here. The data changes rarely (maybe once a year
# when the budget is released).

_EGRANTZ_SCHEMES = [
    {
        "name": "e-Grantz - Post Matric Scholarship for SC Students (Kerala)",
        "description": (
            "Financial assistance for SC students studying in class 11 and above "
            "in recognized institutions in Kerala. Covers tuition fees, "
            "maintenance allowance, and other charges."
        ),
        "eligibility_grade": "11",
        "eligibility_caste": "SC",
        "eligibility_income_max": 250000,
        "benefits": "Full tuition fee + maintenance allowance ₹550-1200/month",
        "url": "https://egrantz.kerala.gov.in",
        "tags": ["Kerala", "SC"],
    },
    {
        "name": "e-Grantz - Pre Matric Scholarship for SC Students (Kerala)",
        "description": (
            "Scholarship for SC students in classes 1-10 studying in Kerala. "
            "Provides stipend and covers educational expenses."
        ),
        "eligibility_grade": "1",
        "eligibility_caste": "SC",
        "eligibility_income_max": 200000,
        "benefits": "Stipend ₹150-350/month + ad hoc grant",
        "url": "https://egrantz.kerala.gov.in",
        "tags": ["Kerala", "SC"],
    },
    {
        "name": "e-Grantz - Post Matric Scholarship for ST Students (Kerala)",
        "description": (
            "Financial aid for ST students in class 11 and above in Kerala. "
            "No income ceiling — all ST students are eligible."
        ),
        "eligibility_grade": "11",
        "eligibility_caste": "ST",
        "eligibility_income_max": None,  # No income ceiling for ST
        "benefits": "Full tuition fee + maintenance allowance ₹550-1200/month",
        "url": "https://egrantz.kerala.gov.in",
        "tags": ["Kerala", "ST"],
    },
    {
        "name": "e-Grantz - Pre Matric Scholarship for ST Students (Kerala)",
        "description": (
            "Scholarship for ST students in classes 1-10 in Kerala. "
            "No income ceiling."
        ),
        "eligibility_grade": "1",
        "eligibility_caste": "ST",
        "eligibility_income_max": None,
        "benefits": "Stipend ₹150-350/month + ad hoc grant",
        "url": "https://egrantz.kerala.gov.in",
        "tags": ["Kerala", "ST"],
    },
    {
        "name": "e-Grantz - Post Matric Scholarship for OBC Students (Kerala)",
        "description": (
            "Post-matric scholarship for OBC students in Kerala. "
            "For students studying in class 11 and above."
        ),
        "eligibility_grade": "11",
        "eligibility_caste": "OBC",
        "eligibility_income_max": 100000,
        "benefits": "Tuition fee reimbursement + maintenance allowance",
        "url": "https://egrantz.kerala.gov.in",
        "tags": ["Kerala", "OBC"],
    },
    {
        "name": "Suvarna Jubilee Merit Scholarship (Kerala)",
        "description": (
            "Merit-based scholarship for students from BPL families who scored "
            "above 50% in SSLC/Plus Two exams. For degree and professional courses."
        ),
        "eligibility_grade": "12",
        "eligibility_caste": None,  # All castes
        "eligibility_income_max": 0,  # BPL only
        "benefits": "₹10,000 - ₹15,000 per year",
        "url": "https://egrantz.kerala.gov.in",
        "tags": ["Kerala", "merit", "BPL"],
    },
    {
        "name": "Prathibha Scholarship (Kerala)",
        "description": (
            "Kerala state merit scholarship for SC/ST students who scored "
            "A+ grade in all subjects in SSLC examination."
        ),
        "eligibility_grade": "11",
        "eligibility_caste": "SC",
        "eligibility_income_max": None,
        "benefits": "₹15,000 for Plus One/Two students, ₹20,000 for degree",
        "url": "https://egrantz.kerala.gov.in",
        "tags": ["Kerala", "SC", "ST", "merit"],
    },
    {
        "name": "Unnathi Scholarship (Kerala)",
        "description": (
            "Scholarship for SC girl students in Kerala pursuing higher education. "
            "Applicable for professional and degree courses."
        ),
        "eligibility_grade": "12",
        "eligibility_caste": "SC",
        "eligibility_income_max": 200000,
        "benefits": "₹10,000 - ₹20,000 per year",
        "url": "https://egrantz.kerala.gov.in",
        "tags": ["Kerala", "SC", "girl child"],
    },
    {
        "name": "KSHEC Scholarship for Economically Backward (Kerala)",
        "description": (
            "Kerala State Higher Education Council scholarship for economically "
            "backward students in higher education. Open to all communities."
        ),
        "eligibility_grade": "12",
        "eligibility_caste": None,
        "eligibility_income_max": 100000,
        "benefits": "₹5,000 - ₹10,000 per year",
        "url": "https://kshec.kerala.gov.in",
        "tags": ["Kerala", "BPL"],
    },
    {
        "name": "Snehapoorvam Scholarship for Orphans (Kerala)",
        "description": (
            "Financial assistance for orphan students in Kerala from "
            "class 1 to post-graduation. Managed by Social Justice Department."
        ),
        "eligibility_grade": "1",
        "eligibility_caste": None,
        "eligibility_income_max": None,
        "benefits": "₹300-1000/month based on class level",
        "url": "https://swd.kerala.gov.in",
        "tags": ["Kerala", "orphan"],
    },
    {
        "name": "Financial Aid for SC/ST Students with Disabilities (Kerala)",
        "description": (
            "Special financial assistance for SC/ST students with disabilities "
            "in Kerala. Additional support on top of regular scholarships."
        ),
        "eligibility_grade": None,
        "eligibility_caste": "SC",
        "eligibility_income_max": None,
        "benefits": "Additional ₹500-1500/month based on disability type",
        "url": "https://egrantz.kerala.gov.in",
        "tags": ["Kerala", "SC", "ST", "disability"],
    },
]


async def scrape_egrantz() -> list[Scholarship]:
    """
    Return curated Kerala SC/ST scholarship data.

    Unlike the other scrapers, this uses a maintained dataset rather than
    live scraping, because e-Grantz doesn't expose a publicly scrapable
    listing page. The data changes rarely (~once/year with budget).
    """
    print("[scraper:egrantz] Loading curated Kerala scholarship data...")

    scholarships = [
        Scholarship(
            name=s["name"],
            source="egrantz",
            description=s["description"],
            eligibility_grade=s["eligibility_grade"],
            eligibility_caste=s["eligibility_caste"],
            eligibility_income_max=s["eligibility_income_max"],
            benefits=s["benefits"],
            url=s["url"],
            tags=s["tags"],
            last_updated=datetime.utcnow(),
        )
        for s in _EGRANTZ_SCHEMES
    ]

    print(f"[scraper:egrantz] Done — {len(scholarships)} scholarships loaded")
    return scholarships
