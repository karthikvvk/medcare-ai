import requests
import json
from sqlalchemy.orm import Session
from datetime import date
from app.core.logging_config import logger
from app.core.config import settings
from app.models.database_models import SKU, DistributionCenter

class ExplanationService:
    def __init__(self):
        pass

    def get_deterministic_explanation(self, action_type: str, sku_name: str, dc_name: str, qty: float, reason_context: dict) -> str:
        """Generates a detailed deterministic explanation using system values."""
        sku_id = reason_context.get("sku_id", "")
        lead_time = reason_context.get("lead_time_days", 5)
        avail = reason_context.get("available_inventory", 0.0)
        rop = reason_context.get("reorder_point", 0.0)
        forecast_7d = reason_context.get("forecast_7d", 0.0)
        days_to_exp = reason_context.get("days_to_expiry", None)
        
        if action_type == "REPLENISH":
            days_of_stock = avail / (forecast_7d / 7.0 + 1e-5)
            explanation = (
                f"{sku_name} ({sku_id}) at {dc_name} requires {qty:.0f} additional units. "
                f"The 7-day demand forecast is {forecast_7d:.0f} units, while available stock is only {avail:.0f} units. "
                f"This represents just {days_of_stock:.1f} days of inventory. Since supplier lead time is {lead_time} days "
                f"and current stock is below the calculated reorder point of {rop:.0f} units, ordering {qty:.0f} units "
                f"is recommended to re-establish the safety stock and prevent stockouts."
            )
        elif action_type == "TRANSFER":
            src_name = reason_context.get("source_dc_name", "another DC")
            dest_name = reason_context.get("destination_dc_name", dc_name)
            explanation = (
                f"Transfer {qty:.0f} units of {sku_name} ({sku_id}) from {src_name} to {dest_name}. "
                f"Analysis shows {src_name} holds excess inventory (batch expiring in {days_to_exp} days), "
                f"while {dest_name} faces a near-term stock shortage below its safety stock levels. "
                f"This transfer rebalances inventory, satisfying demand at {dest_name} and avoiding wastage from expiry at {src_name}."
            )
        elif action_type == "EXPEDITE":
            explanation = (
                f"Expedite incoming order of {sku_name} at {dc_name}. "
                f"A sudden demand surge is projected to exhaust the current stock of {avail:.0f} units "
                f"in {avail / (forecast_7d / 7.0 + 1e-5):.1f} days, which is less than the standard lead time of {lead_time} days. "
                f"Expediting the order is critical to avoid service degradation."
            )
        elif action_type == "MONITOR":
            explanation = (
                f"Monitor inventory of {sku_name} at {dc_name} closely. "
                f"Current inventory is {avail:.0f} units, which is close to the reorder point of {rop:.0f} units. "
                f"No order is scheduled yet, but demand sensing indicates potential regional upward trends."
            )
        else:
            explanation = (
                f"No immediate replenishment required for {sku_name} at {dc_name}. "
                f"Available inventory of {avail:.0f} units is healthy and comfortably exceeds the reorder point of {rop:.0f} units."
            )
        return explanation

    def get_llm_explanation(self, action_type: str, sku_id: str, sku_name: str, dc_name: str, qty: float, reason_context: dict) -> str:
        """
        Queries an LLM provider (OpenAI by default) if LLM_API_KEY is available.
        Otherwise falls back to the deterministic explanation.
        """
        det_explanation = self.get_deterministic_explanation(action_type, sku_name, dc_name, qty, reason_context)
        
        if not settings.LLM_API_KEY:
            return det_explanation
            
        logger.info("Generating LLM-based narrative explanation...")
        
        prompt = (
            f"You are an expert pharmaceutical supply chain assistant. Summarize the following recommendation for an operations manager.\n"
            f"Recommendation Details:\n"
            f"- Action: {action_type}\n"
            f"- SKU: {sku_name} ({sku_id})\n"
            f"- DC: {dc_name}\n"
            f"- Recommended Quantity: {qty}\n"
            f"- Available Inventory: {reason_context.get('available_inventory')}\n"
            f"- Reorder Point: {reason_context.get('reorder_point')}\n"
            f"- 7-day Demand Forecast: {reason_context.get('forecast_7d')}\n"
            f"- Lead Time: {reason_context.get('lead_time_days')} days\n"
            f"- Expiry Days: {reason_context.get('days_to_expiry')}\n"
            f"- Context: {det_explanation}\n\n"
            f"Provide a brief, professional, 2-3 sentence executive summary explaining the 'Why', 'Impact', and 'Next Steps'."
        )
        
        try:
            # Let's support OpenAI API structure
            headers = {
                "Authorization": f"Bearer {settings.LLM_API_KEY}",
                "Content-Type": "application/json"
            }
            data = {
                "model": "gpt-3.5-turbo",
                "messages": [
                    {"role": "system", "content": "You are a professional supply-chain planner. Be concise and precise."},
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": 150,
                "temperature": 0.5
            }
            response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=data, timeout=5)
            if response.status_code == 200:
                result = response.json()
                return result["choices"][0]["message"]["content"].strip()
            else:
                logger.warning(f"LLM API returned status {response.status_code}. Using deterministic explanation.")
                return det_explanation
        except Exception as e:
            logger.warning(f"Failed to fetch LLM explanation: {e}. Falling back to deterministic.")
            return det_explanation

    def generate_executive_summary(self, db: Session, current_date: date) -> str:
        """Generates a text-based natural language summary of the entire supply chain health today."""
        from app.models.database_models import Recommendation, Transfer, Batch
        
        total_recs = db.query(Recommendation).count()
        critical_recs = db.query(Recommendation).filter(Recommendation.priority == "CRITICAL").count()
        high_recs = db.query(Recommendation).filter(Recommendation.priority == "HIGH").count()
        transfers_count = db.query(Transfer).filter(Transfer.status == "RECOMMENDED").count()
        replenish_count = db.query(Recommendation).filter(Recommendation.action_type == "REPLENISH").count()
        
        # Expiry count
        from app.services.expiry_service import ExpiryService
        expiry_service = ExpiryService()
        expiry_reports = expiry_service.simulate_fefo_expiry_risks(db, current_date)
        at_risk_batches = sum(1 for r in expiry_reports if r["risk_level"] in ["CRITICAL", "HIGH"])
        
        summary = (
            f"MedCare Pharma Supply Chain Status Executive Summary (as of {current_date}):\n\n"
            f"Currently, {total_recs} recommendation actions require attention. "
            f"The planning system has detected {critical_recs} CRITICAL stock-out risks and {at_risk_batches} batches with significant expiry risk. "
            f"To rebalance inventory and minimize waste, {transfers_count} inter-DC transfers and {replenish_count} replenishment orders are recommended. "
        )
        
        if critical_recs > 0:
            # Find the highest priority sku
            top_critical = db.query(Recommendation).filter(
                Recommendation.priority == "CRITICAL"
            ).order_by(Recommendation.quantity.desc()).first()
            if top_critical:
                sku = db.query(SKU).filter(SKU.sku_id == top_critical.sku_id).first()
                dc = db.query(DistributionCenter).filter(DistributionCenter.dc_id == top_critical.dc_id).first()
                sku_name = sku.name if sku else top_critical.sku_id
                dc_name = dc.name if dc else top_critical.dc_id
                summary += (
                    f"The highest priority issue is {sku_name} at {dc_name}, where projected demand "
                    f"is significantly exceeding available inventory. Immediate replenishment of {top_critical.quantity:.0f} units is recommended."
                )
        else:
            summary += "Overall supply chain health is stable. No critical stock-out alerts were triggered."
            
        return summary
