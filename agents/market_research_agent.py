from services.claude_service import invoke_llm

def market_research_agent(
    business_name: str,
    industry: str,
    country: str,
    purpose: str,
    description: str
) -> str:
    prompt = f"""You are an expert Market Research Consultant.
Analyze the following business and generate a comprehensive market research report.

Business Name: {business_name}
Industry: {industry}
Country: {country}
Purpose: {purpose}
Description: {description}

Generate the following sections in Markdown format:

## 1. Executive Summary
## 2. Market Overview
- Market size (TAM, SAM, SOM)
- Growth rate and CAGR
## 3. Target Customers
- Demographics and psychographics
- Customer segments
## 4. Industry Trends
- Current trends
- Future outlook
## 5. Competitor Analysis
| Competitor | Strengths | Weaknesses | Market Share |
## 6. Market Opportunities
## 7. Market Risks
## 8. Conclusion & Recommendations

Use markdown tables where appropriate. Be specific to {country} market.
"""
    return invoke_llm(prompt)