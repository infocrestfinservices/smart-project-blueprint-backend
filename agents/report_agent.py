from services.claude_service import invoke_llm

def report_agent(
    business_name: str,
    industry: str,
    country: str,
    purpose: str,
    description: str,
    market_research: str,
    feasibility: str,
    swot: str,
    project_cost: float = 0,
    own_contribution: float = 0,
    loan_amount: float = 0
) -> str:
    prompt = f"""You are an expert Business Report Writer.
Compile a professional project report using the analysis below.

Business: {business_name}
Industry: {industry}
Country: {country}
Purpose: {purpose}
Description: {description}
Project Cost: {project_cost:,.0f}
Own Contribution: {own_contribution:,.0f}
Loan Required: {loan_amount:,.0f}

MARKET RESEARCH:
{market_research}

FEASIBILITY ANALYSIS:
{feasibility}

SWOT ANALYSIS:
{swot}

Generate a complete professional report with:
## 1. Executive Summary
## 2. Business Overview
## 3. Market Analysis Summary
## 4. Feasibility Assessment
## 5. SWOT Summary
## 6. Financial Overview
| Particulars | Amount |
|---|---|
| Total Project Cost | {project_cost:,.0f} |
| Own Contribution | {own_contribution:,.0f} |
| Loan Required | {loan_amount:,.0f} |

## 7. Risk Assessment
## 8. Conclusion & Recommendations

Return professional Markdown report.
"""
    return invoke_llm(prompt)