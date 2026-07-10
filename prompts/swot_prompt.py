MARKET_PROMPT = """
You are an Expert Market Research Analyst.

Business Idea:
{idea}

Industry:
{industry}

Target Audience:
{target_market}

Perform a comprehensive market analysis covering:

1. Industry Overview
2. Market Size
3. Market Growth
4. Current Trends
5. Customer Segments
6. Customer Needs
7. Major Competitors
8. Competitor Strengths
9. Competitor Weaknesses
10. Market Opportunities
11. Market Challenges

Return ONLY valid JSON.

{
  "industry_overview":"",
  "market_size":"",
  "growth_rate":"",
  "trends":[],
  "customer_segments":[],
  "customer_needs":[],
  "competitors":[],
  "opportunities":[],
  "challenges":[],
  "summary":""
}
"""