QUERY_BANK = {
    "emergency": {
        "priority": "CRITICAL",
        "priority_num": 1,
        "queries": [
            "elevator out of service what to do",
            "emergency elevator repair {city}",
            "elevator stuck between floors who to call",
            "how fast can elevator be repaired",
            "24 hour elevator repair service",
            "elevator emergency phone number",
            "elevator breakdown immediate response",
            "elevator entrapment rescue procedure",
        ],
    },
    "research_evaluation": {
        "priority": "HIGH",
        "priority_num": 3,
        "queries": [
            "best elevator maintenance company {city}",
            "how much does elevator maintenance cost",
            "how often should elevators be inspected",
            "elevator modernization vs replacement cost",
            "what is included in elevator maintenance contract",
            "elevator service company vs OEM manufacturer",
            "how to switch elevator maintenance company",
            "elevator maintenance contract pricing",
            "independent elevator service vs OEM",
            "elevator service provider comparison",
            "how to evaluate elevator service company",
            "elevator maintenance ROI",
            "elevator modernization cost breakdown",
            "full maintenance vs oil and grease contract",
        ],
    },
    "compliance_regulatory": {
        "priority": "HIGH",
        "priority_num": 3,
        "queries": [
            "elevator inspection requirements {state}",
            "ADA elevator requirements for buildings",
            "elevator code violation penalties",
            "how to pass elevator inspection",
            "ASME A17.1 elevator code explained",
            "elevator safety code compliance",
            "state elevator inspection frequency",
            "elevator certificate of compliance",
            "elevator inspection checklist",
            "elevator code update requirements",
        ],
    },
    "vertical_specific": {
        "priority": "HIGH",
        "priority_num": 3,
        "queries": [
            "hospital elevator requirements and maintenance",
            "hotel elevator maintenance best practices",
            "apartment building elevator maintenance requirements",
            "commercial building elevator service contract",
            "university elevator ADA compliance",
            "healthcare facility elevator code",
            "multifamily elevator modernization",
            "office building elevator inspection schedule",
            "senior living elevator requirements",
            "retail elevator maintenance standards",
        ],
    },
    "comparison_decision": {
        "priority": "MEDIUM",
        "priority_num": 5,
        "queries": [
            "elevator modernization vs full replacement",
            "OEM vs independent elevator service pros and cons",
            "full maintenance vs oil and grease contract",
            "how to evaluate and switch elevator service vendor",
            "elevator service contract negotiation tips",
        ],
    },
    "data_statistics": {
        "priority": "MEDIUM",
        "priority_num": 5,
        "queries": [
            "elevator industry statistics 2025",
            "elevator downtime cost statistics",
            "elevator maintenance cost benchmarks",
            "elevator accident statistics",
            "elevator modernization ROI statistics",
        ],
    },
}


def get_all_queries() -> list[dict]:
    results = []
    for category, data in QUERY_BANK.items():
        for q in data["queries"]:
            results.append(
                {
                    "query": q,
                    "category": category,
                    "priority": data["priority"],
                    "priority_num": data["priority_num"],
                }
            )
    return results


def interpolate_query(query: str, city: str = "", state: str = "") -> str:
    return query.replace("{city}", city).replace("{state}", state)
