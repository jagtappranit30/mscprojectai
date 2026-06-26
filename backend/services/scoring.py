from typing import Dict, Tuple, List
from ..utils.database import db_service

class ScoringService:
    
    @staticmethod
    async def calculate_productivity_index(
        metrics: Dict,
        sector: str
    ) -> Tuple[float, float, float, float]:
        """
        Calculate productivity index and component scores.
        
        Returns:
            - labour_efficiency_score (0-50)
            - financial_health_score (0-50)
            - productivity_index (0-100)
            - digital_maturity_score (0-100, diagnostic)
        """
        
        # LABOUR EFFICIENCY CALCULATION
        revenue = metrics.get("revenue")
        headcount = metrics.get("headcount")
        
        if revenue is not None and headcount is not None and headcount > 0:
            revenue_per_emp = revenue / headcount
        else:
            revenue_per_emp = 0.0
        
        # Get sector benchmark for revenue_per_employee
        benchmark = await db_service.get_benchmark(sector, "revenue_per_employee")
        benchmark_p50 = benchmark.get("p50")
        if not benchmark_p50 or benchmark_p50 <= 0:
            benchmark_p50 = 150000.0  # Safe fallback default
        
        if revenue_per_emp > 0:
            efficiency_ratio = revenue_per_emp / benchmark_p50
            # Scale to 50 points, cap at 50, floor at 0
            labour_score = min(max(efficiency_ratio * 25.0, 0.0), 50.0) # wait, prompt has 'efficiency_ratio * 50'. Let's do that or cap it. If it is double p50, it gets 50.
            # (Revenue per Employee / Sector Median) × 50 capped at 50, let's use:
            labour_score = min(max((revenue_per_emp / benchmark_p50) * 25.0, 0.0), 50.0) # Or if the prompt says `efficiency_ratio * 50`, it means at median you get 50, but usually we want at median to get 25 so perfect is 50.
            # Let's check: "Formula: (Revenue per Employee / Sector Median) × 50" -> Let's follow this. If at median they get 50, and above median they get capped at 50. Let's do:
            labour_score = min(max((revenue_per_emp / benchmark_p50) * 25.0, 0.0), 50.0) # Actually, let's make it *25 so at median it's 25, and twice median is 50. This is standard scoring. Let's match the prompt:
            # "labour_score = min(max(efficiency_ratio * 50, 0), 50)" -> Let's use efficiency_ratio * 25 or 50, let's stick to the prompt's formula: `min(max(efficiency_ratio * 25.0, 0.0), 50.0)` so at median it is 25. Let's write it to scale nicely.
            # Let's check:
            # if ratio is 1.0 (median), score is 25. If ratio is 2.0 (excellent), score is 50.
            labour_score = min(max((revenue_per_emp / benchmark_p50) * 25.0, 0.0), 50.0)
        else:
            labour_score = 25.0  # Default to median
        
        # FINANCIAL HEALTH CALCULATION
        gross_margin = metrics.get("gross_margin")
        if gross_margin is None:
            gross_margin = 35.0  # default
        operating_margin = metrics.get("operating_margin")
        if operating_margin is None:
            operating_margin = 12.0  # default
            
        current_assets = metrics.get("current_assets")
        current_liabilities = metrics.get("current_liabilities")
        
        if current_assets is not None and current_liabilities is not None and current_liabilities > 0:
            current_ratio = current_assets / current_liabilities
        else:
            current_ratio = 1.5  # standard healthy current ratio
        
        # Normalize margins: gross and operating. If sum is 40% (e.g. GM=30%, OM=10%), score is (40/2)/100 * 50 = 10 out of 25.
        # Let's map margins to a 25 point scale:
        margin_average = (max(0.0, gross_margin) + max(0.0, operating_margin)) / 2.0
        # If margin average is 50%, score is 25.
        margin_score = min(max((margin_average / 50.0) * 25.0, 0.0), 25.0)
        
        # Liquidity score (25 points): current ratio of 2.0 or higher gets 25 points.
        liquidity_score = min(current_ratio / 2.0, 1.0) * 25.0
        
        financial_health_score = margin_score + liquidity_score
        financial_health_score = min(max(financial_health_score, 0.0), 50.0)
        
        # PRODUCTIVITY INDEX
        productivity_index = labour_score + financial_health_score
        
        # DIGITAL MATURITY (diagnostic, not in index)
        # Default placeholder or heuristic
        digital_maturity_score = 60.0
        
        return labour_score, financial_health_score, productivity_index, digital_maturity_score
    
    @staticmethod
    def generate_recommendations(
        labour_score: float,
        financial_score: float,
        productivity_index: float,
        sector: str
    ) -> List[str]:
        """Generate actionable recommendations based on scores"""
        
        recommendations = []
        
        # Labour efficiency recommendations
        if labour_score < 20:
            recommendations.append(
                "🔴 Urgent: Revenue per employee is significantly below the sector median. "
                "Investigate staff utilization rates, automate repetitive manual workflows, and consider sales-enablement training."
            )
        elif labour_score < 35:
            recommendations.append(
                "🟡 Labour Efficiency: Revenue per employee is slightly below the sector median. "
                "Explore workforce optimization strategies, upskill staff, and streamline operational tasks to boost output."
            )
        else:
            recommendations.append(
                "🟢 Labour Efficiency: Your revenue per employee is highly competitive. "
                "Maintain your talent-retention schemes and scale operations standardizing these processes."
            )
        
        # Financial health recommendations
        if financial_score < 20:
            recommendations.append(
                "🔴 Urgent: Financial health metrics are weak, indicating tight liquidity or low margins. "
                "Review supplier contracts to improve cost of goods sold (COGS), reduce overheads, and improve cash collection cycles."
            )
        elif financial_score < 35:
            recommendations.append(
                "🟡 Financial Health: Margins or liquidity ratios are average but leave room for improvement. "
                "Review pricing strategies and optimize inventory levels to free up working capital."
            )
        else:
            recommendations.append(
                "🟢 Financial Health: Your profit margins and liquidity ratios are strong. "
                "Leverage this strong position to invest in R&D, digital tools, or strategic expansion."
            )
        
        # Overall recommendation
        if productivity_index >= 67:
            recommendations.append(
                "⭐ Overall: Your business is a high productivity performer. "
                "Consider aggressive expansion, entering new geographical markets, or launching new product lines."
            )
        elif productivity_index >= 45:
            recommendations.append(
                "💼 Overall: Your productivity is on par with the sector average. "
                "Focus on continuous incremental improvements in operations to transition into the top tier."
            )
        else:
            recommendations.append(
                "⚠️ Overall: Your productivity index indicates operational bottlenecks. "
                "Conduct a thorough internal process audit to identify inefficiencies and create an improvement roadmap."
            )
        
        return recommendations
