from services.claude_service import invoke_llm

def feasibility_agent(
    business_name: str,
    industry: str,
    country: str,
    description: str,
    project_cost: float = 0,
    own_contribution: float = 0,
    loan_amount: float = 0
) -> str:
    prompt = f"""You are a Feasibility Study Consultant.
Evaluate this business and provide a detailed feasibility analysis.

Business: {business_name}
Industry: {industry}
Country: {country}
Description: {description}
Total Project Cost: {project_cost:,.0f}
Own Contribution: {own_contribution:,.0f}
Loan Required: {loan_amount:,.0f}

Score each category out of 100 and explain:

## Feasibility Scores

| Category | Score (/100) | Assessment |
|----------|-------------|------------|
| Market Potential | | |
| Financial Feasibility | | |
| Operational Feasibility | | |
| Technical Feasibility | | |
| Competitive Position | | |
| Risk Level | | |

## Overall Feasibility Score: X/100

## Recommendation
(Choose one: Highly Feasible / Moderately Feasible / Needs Review / Not Feasible)

## Detailed Analysis
Explain reasoning for each score.

## Key Success Factors

## Major Risks & Mitigation

Return in Markdown format.
"""
    return invoke_llm(prompt)