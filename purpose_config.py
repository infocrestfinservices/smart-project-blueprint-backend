"""
purpose_config.py

Central, purpose-driven registry. The selected business *purpose* drives the
entire generation pipeline: which extra questions to ask, which Word report
sections to write, which Excel worksheets to build, and which dashboard charts
to plot. Nothing about the report structure is hardcoded into the generators —
they read it from here.

Add a new purpose by adding one entry to PURPOSES.
"""

# ── Canonical purpose keys ────────────────────────────────────────────────
FEASIBILITY = "feasibility_study"
CMA = "cma_data"
IRR = "irr_analysis"
IMMIGRATION = "immigration_business_plan"
REAL_ESTATE = "real_estate"
STARTUP = "startup_sme_fundraising"
GENERIC = "generic"


def resolve_purpose(purpose: str = None, financial_format: str = None) -> str:
    """Map the app's free-form purpose / financial_format onto a canonical key.

    The questionnaire stores values like 'bank_loan' + financial_format
    'cma_india', or 'venture_capital'. We fold those onto the modelling key
    that best matches the CA methodology.
    """
    p = (purpose or "").lower().strip()
    f = (financial_format or "").lower().strip()

    if "immigration" in p:
        return IMMIGRATION
    if "real" in p and "estate" in p:
        return REAL_ESTATE
    if "fundrais" in p or "startup" in p or "sme" in p:
        return STARTUP
    if "cma" in p or "cma" in f:
        return CMA
    if p in ("feasibility_study", "feasibility", "internal_planning"):
        return FEASIBILITY
    # Startup investment purposes generate the fundraising financial model.
    if p in ("venture_capital", "angel_investment"):
        return STARTUP
    if p in ("irr_analysis", "irr") or f.startswith("investor"):
        return IRR
    if "loan" in p or "project_finance" in p or "dpr" in p:
        # Loan / DPR / project-finance use the CMA-style banking model by default.
        return CMA
    return GENERIC


# ── Per-purpose definitions ───────────────────────────────────────────────
# question:    {key, label, type ('number'|'text'|'percent'), hint}
# word_section:{title, guidance}  -> guides the narrative the agents write
# excel_sheet: {name, purpose}    -> guides the AI's structured rows for that sheet
# chart:       {title, type ('bar'|'line'|'pie'), sheet, x, series}
#              x = column header for categories; series = list of column headers

PURPOSES = {
    FEASIBILITY: {
        "label": "Feasibility Study",
        "questions": [
            {"key": "land_cost", "label": "Land Cost", "type": "number", "hint": "Cost of land / site"},
            {"key": "building_cost", "label": "Building & Civil Cost", "type": "number", "hint": "Construction cost"},
            {"key": "machinery_cost", "label": "Plant & Machinery Cost", "type": "number", "hint": "Equipment cost"},
            {"key": "production_capacity", "label": "Production Capacity", "type": "text", "hint": "Units per year / installed capacity"},
            {"key": "raw_material_cost", "label": "Annual Raw Material Cost", "type": "number", "hint": "Yearly RM cost at full capacity"},
            {"key": "utility_cost", "label": "Annual Utility Cost", "type": "number", "hint": "Power, water, fuel per year"},
            {"key": "labour_cost", "label": "Annual Labour Cost", "type": "number", "hint": "Wages & salaries per year"},
            {"key": "selling_price", "label": "Selling Price per Unit", "type": "number", "hint": "Average realisation per unit"},
            {"key": "market_demand", "label": "Market Demand", "type": "text", "hint": "Estimated demand / market size"},
            {"key": "production_process", "label": "Production Process", "type": "text", "hint": "Brief on the process / technology"},
        ],
        "word_sections": [
            {"title": "Executive Summary", "guidance": "Concise overview of the project, viability verdict, and headline numbers."},
            {"title": "Project Overview", "guidance": "Promoter background, location, product/service, capacity."},
            {"title": "Technical Feasibility", "guidance": "Production process, technology, plant & machinery, capacity, location suitability, infrastructure."},
            {"title": "Economic Feasibility", "guidance": "Market demand, pricing, competition, demand-supply gap, economic justification."},
            {"title": "Operational Feasibility", "guidance": "Manpower, raw material availability, utilities, logistics, management capability."},
            {"title": "Financial Feasibility", "guidance": "Cost of project, means of finance, profitability, break-even, return indicators. Refer to the Excel model for detailed figures."},
            {"title": "Risk Analysis", "guidance": "Key risks (market, financial, operational, regulatory) with mitigation measures."},
            {"title": "Recommendations", "guidance": "Clear go / no-go recommendation with conditions and next steps."},
        ],
        "excel_sheets": [
            {"name": "Assumptions", "purpose": "Key inputs & assumptions: capacity utilisation %, price, cost escalation %, interest rate, tax rate, project life."},
            {"name": "Capital Cost", "purpose": "Cost of project line items (Land, Building, Machinery, Pre-op, Contingency, Working Capital Margin) with amounts and % of total."},
            {"name": "Operating Cost", "purpose": "Annual operating costs (Raw Material, Utilities, Labour, Admin, Selling, Maintenance) projected over 5 years."},
            {"name": "Revenue Projection", "purpose": "Year 1-5 revenue: capacity, utilisation %, units sold, price, total revenue."},
            {"name": "Cash Flow", "purpose": "Year 1-5 cash flow: revenue, operating cost, EBITDA, depreciation, interest, PBT, tax, PAT, net cash flow."},
            {"name": "Break-even Analysis", "purpose": "Fixed cost, variable cost per unit, contribution, break-even units and break-even %."},
            {"name": "Sensitivity Analysis", "purpose": "Impact on profitability/NPV of +/-10% changes in price, volume, and cost."},
        ],
        "charts": [
            {"title": "Revenue vs Operating Cost (5Y)", "type": "line", "sheet": "Cash Flow", "x": "Particulars", "series": ["Revenue", "Operating Cost"]},
            {"title": "Capital Cost Breakdown", "type": "pie", "sheet": "Capital Cost", "x": "Particulars", "series": ["Amount"]},
            {"title": "PAT Trend (5Y)", "type": "bar", "sheet": "Cash Flow", "x": "Particulars", "series": ["PAT"]},
        ],
    },

    CMA: {
        "label": "CMA Data",
        "questions": [
            {"key": "loan_amount", "label": "Term Loan Amount Requested", "type": "number", "hint": "Bank loan sought"},
            {"key": "existing_borrowings", "label": "Existing Borrowings", "type": "number", "hint": "Current outstanding loans"},
            {"key": "working_capital_requirement", "label": "Working Capital Requirement", "type": "number", "hint": "Estimated WC need"},
            {"key": "current_assets", "label": "Current Assets", "type": "number", "hint": "Inventory + debtors + cash + other CA"},
            {"key": "current_liabilities", "label": "Current Liabilities", "type": "number", "hint": "Creditors + short-term dues"},
            {"key": "projected_sales", "label": "Projected Annual Sales", "type": "number", "hint": "Next-year turnover"},
            {"key": "projected_expenses", "label": "Projected Annual Expenses", "type": "number", "hint": "Next-year operating expenses"},
            {"key": "inventory", "label": "Inventory", "type": "number", "hint": "Closing stock value"},
            {"key": "debtors", "label": "Sundry Debtors", "type": "number", "hint": "Receivables"},
            {"key": "creditors", "label": "Sundry Creditors", "type": "number", "hint": "Payables"},
            {"key": "bank_name", "label": "Banking Details", "type": "text", "hint": "Bank & branch the proposal is for"},
        ],
        "word_sections": [
            {"title": "Executive Summary", "guidance": "Borrower profile, facility requested, and credit recommendation in brief."},
            {"title": "Borrower & Banking Information", "guidance": "Constitution, management, banking arrangement, existing facilities, conduct of account."},
            {"title": "Financial Statements Overview", "guidance": "Narrative on the projected P&L and balance sheet trends. Figures are in the Excel model."},
            {"title": "Working Capital Analysis", "guidance": "Working capital cycle, holding levels, MPBF computation method (Tandon II), and assessed limit."},
            {"title": "Ratio Analysis", "guidance": "Current ratio, DSCR, TOL/TNW, debt-equity — interpretation against bank benchmarks."},
            {"title": "Loan Assessment & Recommendation", "guidance": "Eligibility, security, repayment capacity, and recommendation."},
        ],
        "excel_sheets": [
            {"name": "Borrower Details", "purpose": "Borrower name, constitution, activity, bank/branch, facility requested, existing borrowings."},
            {"name": "Project Cost", "purpose": "Cost of project line items with amounts and % of total."},
            {"name": "Means of Finance", "purpose": "Promoter contribution, term loan, working capital loan; show debt-equity ratio and promoter %."},
            {"name": "Profit & Loss", "purpose": "Projected P&L for 2 past + 3 projected years: net sales, cost of sales, gross profit, expenses, depreciation, interest, PBT, tax, PAT."},
            {"name": "Projected Balance Sheet", "purpose": "Liabilities (capital, reserves, term loan, WC loan, creditors) and Assets (fixed assets, inventory, debtors, cash) over 2+3 years; totals must balance."},
            {"name": "Cash Flow", "purpose": "Sources and uses of funds with opening/closing cash for each year."},
            {"name": "Working Capital", "purpose": "Current assets and current liabilities build-up; net working capital and working capital gap."},
            {"name": "MPBF", "purpose": "Maximum Permissible Bank Finance (Tandon Method II): current assets, current liabilities, 25% margin, MPBF."},
            {"name": "Financial Ratios", "purpose": "Current ratio, DSCR, TOL/TNW, debt-equity, net profit margin per year, with bank benchmark column."},
        ],
        "charts": [
            {"title": "Sales vs PAT (Projected)", "type": "line", "sheet": "Profit & Loss", "x": "Particulars", "series": ["Net Sales", "PAT"]},
            {"title": "Means of Finance", "type": "pie", "sheet": "Means of Finance", "x": "Particulars", "series": ["Amount"]},
            {"title": "Current Ratio Trend", "type": "bar", "sheet": "Financial Ratios", "x": "Ratio", "series": ["Year 1", "Year 2", "Year 3"]},
        ],
    },

    IRR: {
        "label": "IRR Analysis",
        "questions": [
            {"key": "initial_investment", "label": "Initial Investment", "type": "number", "hint": "Upfront capital outlay"},
            {"key": "discount_rate", "label": "Discount Rate", "type": "percent", "hint": "Cost of capital / hurdle rate %"},
            {"key": "project_life", "label": "Project Life (years)", "type": "number", "hint": "Evaluation horizon"},
            {"key": "salvage_value", "label": "Salvage Value", "type": "number", "hint": "Residual value at end of life"},
            {"key": "operating_cost", "label": "Annual Operating Cost", "type": "number", "hint": "Yearly opex"},
            {"key": "annual_revenue", "label": "Annual Revenue", "type": "number", "hint": "Year-1 revenue"},
            {"key": "tax_rate", "label": "Tax Rate", "type": "percent", "hint": "Corporate tax %"},
            {"key": "inflation_rate", "label": "Inflation Rate", "type": "percent", "hint": "Annual escalation %"},
            {"key": "maintenance_cost", "label": "Annual Maintenance Cost", "type": "number", "hint": "Yearly maintenance"},
        ],
        "word_sections": [
            {"title": "Investment Summary", "guidance": "Project, initial outlay, financing, and headline return metrics (IRR, NPV, payback)."},
            {"title": "Assumptions & Methodology", "guidance": "Discount rate, project life, growth/inflation, tax, salvage — and the DCF methodology used."},
            {"title": "Cash Flow Analysis", "guidance": "Narrative on the year-by-year free cash flows. Figures are in the Excel model."},
            {"title": "NPV & IRR", "guidance": "Interpretation of NPV at the chosen discount rate and the IRR vs hurdle rate."},
            {"title": "Payback Period", "guidance": "Simple and discounted payback period interpretation."},
            {"title": "Sensitivity Analysis", "guidance": "How IRR/NPV move with revenue, cost, and discount-rate changes."},
            {"title": "Recommendation", "guidance": "Invest / do-not-invest verdict with rationale."},
        ],
        "excel_sheets": [
            {"name": "Assumptions", "purpose": "Initial investment, discount rate, project life, salvage, tax %, inflation %, revenue growth %."},
            {"name": "Investment Cost", "purpose": "Capital cost breakdown with amounts and % of total."},
            {"name": "Funding Pattern", "purpose": "Equity vs debt split, amounts and %, with debt-equity ratio."},
            {"name": "Cash Flow", "purpose": "Year 0-N free cash flows: revenue, operating cost, maintenance, depreciation, PBT, tax, PAT, add depreciation, net cash flow, salvage in final year."},
            {"name": "NPV", "purpose": "Discount factor and present value of each year's cash flow at the discount rate; cumulative NPV."},
            {"name": "IRR", "purpose": "Cash flow series used for IRR and the computed IRR %."},
            {"name": "Payback Period", "purpose": "Cumulative cash flow by year showing simple and discounted payback."},
            {"name": "DSCR", "purpose": "If debt-funded: cash available for debt service vs debt obligations per year, with DSCR."},
            {"name": "Sensitivity Analysis", "purpose": "IRR/NPV under -10%/base/+10% revenue and cost scenarios."},
        ],
        "charts": [
            {"title": "Net Cash Flow by Year", "type": "bar", "sheet": "Cash Flow", "x": "Particulars", "series": ["Net Cash Flow"]},
            {"title": "Cumulative NPV", "type": "line", "sheet": "NPV", "x": "Year", "series": ["Cumulative PV"]},
            {"title": "Funding Pattern", "type": "pie", "sheet": "Funding Pattern", "x": "Particulars", "series": ["Amount"]},
        ],
    },

    GENERIC: {
        "label": "Business Report",
        "questions": [
            {"key": "project_cost", "label": "Total Project Cost", "type": "number", "hint": "Total capital required"},
            {"key": "annual_revenue", "label": "Expected Annual Revenue", "type": "number", "hint": "Year-1 revenue"},
            {"key": "operating_cost", "label": "Annual Operating Cost", "type": "number", "hint": "Yearly running cost"},
            {"key": "own_contribution", "label": "Own Contribution", "type": "number", "hint": "Promoter equity"},
            {"key": "loan_amount", "label": "Loan / Funding Required", "type": "number", "hint": "External funding"},
        ],
        "word_sections": [
            {"title": "Executive Summary", "guidance": "Overview and key takeaways."},
            {"title": "Business Overview", "guidance": "Promoter, product/service, location, market."},
            {"title": "Market Analysis", "guidance": "Demand, competition, opportunity."},
            {"title": "Financial Overview", "guidance": "Cost, funding, profitability. Detailed figures are in the Excel model."},
            {"title": "Risk Assessment", "guidance": "Key risks and mitigation."},
            {"title": "Conclusion & Recommendations", "guidance": "Verdict and next steps."},
        ],
        "excel_sheets": [
            {"name": "Assumptions", "purpose": "Key inputs: revenue, cost, growth %, interest, tax, project life."},
            {"name": "Project Cost", "purpose": "Cost of project line items with amounts and % of total."},
            {"name": "Means of Finance", "purpose": "Equity vs debt with debt-equity ratio."},
            {"name": "Profitability", "purpose": "Year 1-5 revenue, cost, EBITDA, PAT."},
            {"name": "Cash Flow", "purpose": "Year 1-5 net cash flow."},
        ],
        "charts": [
            {"title": "Revenue vs PAT (5Y)", "type": "line", "sheet": "Profitability", "x": "Particulars", "series": ["Revenue", "PAT"]},
            {"title": "Project Cost Breakdown", "type": "pie", "sheet": "Project Cost", "x": "Particulars", "series": ["Amount"]},
        ],
    },

    # The 3 template-driven purposes below build their Excel model by FILLING a
    # sample workbook (see template_config / template_fill_service), so they carry
    # no LLM excel_sheets/charts — only the narrative sections for the Word report.
    IMMIGRATION: {
        "label": "Immigration Business Plan",
        "questions": [],
        "word_sections": [
            {"title": "Executive Summary", "guidance": "Applicant, business concept, investment, and headline projections for the visa authority."},
            {"title": "Business Overview", "guidance": "Product/service, business model, location and legal structure in the destination country."},
            {"title": "Market Analysis", "guidance": "Target market, demand, and competition in the destination country."},
            {"title": "Management & Job Creation", "guidance": "Founder background, org structure, and the jobs the business will create (key for immigration)."},
            {"title": "Financial Plan", "guidance": "Investment, funding, revenue and profitability projections. Detailed figures are in the Excel model."},
            {"title": "Conclusion", "guidance": "Viability and alignment with the visa programme's requirements."},
        ],
        "excel_sheets": [],
        "charts": [],
    },

    REAL_ESTATE: {
        "label": "Real Estate Financial Model",
        "questions": [],
        "word_sections": [
            {"title": "Executive Summary", "guidance": "Project, total development cost, financing, and headline returns (IRR, equity multiple, yield)."},
            {"title": "Project Overview", "guidance": "Asset type, location, unit/room mix, timeline, and development scope."},
            {"title": "Market Analysis", "guidance": "Submarket demand, rents/prices, absorption, and comparable assets."},
            {"title": "Development Budget & Financing", "guidance": "Hard/soft costs, sources & uses, debt terms, and equity structure. Figures are in the Excel model."},
            {"title": "Returns & Exit", "guidance": "Cash flow, valuation, exit assumptions, and investor returns."},
            {"title": "Risk & Recommendation", "guidance": "Key risks (market, construction, financing) and the investment recommendation."},
        ],
        "excel_sheets": [],
        "charts": [],
    },

    STARTUP: {
        "label": "Startup & SME Fundraising",
        "questions": [],
        "word_sections": [
            {"title": "Executive Summary", "guidance": "Company, raise amount, use of funds, and headline metrics (revenue, growth, valuation)."},
            {"title": "Business & Product", "guidance": "Problem, solution/product, business model, and traction to date."},
            {"title": "Market Opportunity", "guidance": "TAM/SAM/SOM, target segments, and competitive landscape."},
            {"title": "Financial Projections", "guidance": "Revenue build-up, unit economics, cost structure and path to profitability. Figures are in the Excel model."},
            {"title": "Funding Ask & Use of Funds", "guidance": "Amount raised, instrument, valuation, and how the capital is deployed."},
            {"title": "Investor Returns & Exit", "guidance": "Return scenarios and potential exit paths."},
        ],
        "excel_sheets": [],
        "charts": [],
    },
}


def get_config(purpose_key: str) -> dict:
    return PURPOSES.get(purpose_key, PURPOSES[GENERIC])
