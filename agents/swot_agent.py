from services.claude_service import invoke_llm

def swot_agent(
    business_name: str,
    industry: str,
    country: str,
    description: str
) -> str:
    prompt = f"""You are a Business Strategy Consultant.
Create a detailed SWOT analysis for this business.

Business Name: {business_name}
Industry: {industry}
Country: {country}
Description: {description}

Generate a comprehensive SWOT analysis:

## SWOT Analysis — {business_name}

### Strengths
(Internal positive factors — list at least 5 specific points)

### Weaknesses
(Internal negative factors — list at least 5 specific points)

### Opportunities
(External positive factors — list at least 5 specific points)

### Threats
(External negative factors — list at least 5 specific points)

## Strategic Recommendations
Based on the SWOT, provide 3-5 strategic recommendations.

## SWOT Matrix Summary
| | Positive | Negative |
|---|---|---|
| Internal | Strengths | Weaknesses |
| External | Opportunities | Threats |

Be specific to the {industry} industry in {country}.
Return in Markdown format.
"""
    return invoke_llm(prompt)