import os
import json
import uuid
import requests
import threading
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.logging_config import logger
from app.models.database_models import SKU, DistributionCenter, InventorySnapshot, Recommendation, Transfer
from app.services.inventory_service import InventoryService

class OllamaCloudClient:
    """
    Calls the Ollama cloud API (https://ollama.com/api) using the exact same
    wire format as a local Ollama server, but authenticates with an API key
    obtained from https://ollama.com/settings/keys.
    """

    @staticmethod
    def is_available() -> bool:
        """Returns True when an Ollama cloud API key is configured."""
        return bool(settings.OLLAMA_API_KEY)

    @staticmethod
    def check_status() -> dict:
        """Returns Ollama cloud connectivity status."""
        available = OllamaCloudClient.is_available()
        return {
            "is_connected": available,
            "host": settings.OLLAMA_HOST,
            "model": settings.OLLAMA_MODEL,
            "is_model_available": available,
        }

    @staticmethod
    def generate(prompt: str, temperature: float = 0.2) -> str | None:
        """
        Posts to the Ollama cloud /api/chat endpoint.
        Returns the assistant message content string on success, None on failure.
        Callers fall back to the deterministic heuristics engine on None.

        NOTE: Ollama Cloud exposes /api/chat (not /api/generate) and requires
        the messages-array payload. The response is in message.content.
        """
        if not OllamaCloudClient.is_available():
            logger.warning("Ollama Cloud: OLLAMA_API_KEY is not set — skipping LLM call.")
            return None
        try:
            headers = {
                "Authorization": f"Bearer {settings.OLLAMA_API_KEY}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": settings.OLLAMA_MODEL,
                "messages": [
                    {
                        "role": "system",
                        "content": "You are a helpful assistant. Always respond with valid JSON only — no markdown, no explanation, no extra text.",
                    },
                    {"role": "user", "content": prompt},
                ],
                "stream": False,
                "options": {"temperature": temperature},
            }
            res = requests.post(
                f"{settings.OLLAMA_HOST}/api/chat",
                headers=headers,
                json=payload,
                timeout=120,
            )
            if res.status_code == 200:
                content = res.json().get("message", {}).get("content")
                logger.info(f"Ollama Cloud responded successfully (model={settings.OLLAMA_MODEL})")
                return content
            else:
                logger.warning(
                    f"Ollama Cloud returned HTTP {res.status_code} for model '{settings.OLLAMA_MODEL}': {res.text[:300]}"
                )
                return None
        except Exception as e:
            logger.warning(f"Ollama Cloud request failed: {e}")
            return None


def _clean_json_str(raw: str) -> dict | None:
    """Parses JSON from LLM output, handling markdown fences and extraneous text."""
    if not raw:
        return None
    cleaned = raw.strip()
    # Strip markdown code blocks ```json ... ```
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()
    
    try:
        return json.loads(cleaned)
    except Exception:
        pass
        
    # Extract JSON object substring
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(cleaned[start:end+1])
        except Exception:
            pass
    return None


# Alias used by routes_live_scenario.py
OllamaManager = OllamaCloudClient
CloudLLMClient = OllamaCloudClient



class LiveScenarioService:
    # Mode configurations: 'AUTO', 'SIMULATED', 'NEWS'
    _active_mode = 'AUTO'
    
    # In-memory storage for active manual simulation
    _simulated_event = None
    _simulated_region = None
    _simulated_area = None
    _simulated_severity = None
    
    # Store fetched news headlines and AI scenario extracted from it
    _news_headlines = []
    _news_scenario = None
    
    # Store the last analysis recommendations and transfers for committing
    _last_analysis_results = None

    DC_MAPPING = {
        "chennai": "DC001",
        "bangalore": "DC002",
        "hyderabad": "DC003",
        "mumbai": "DC004",
        "delhi": "DC005",
        "kolkata": "DC006",
        "pune": "DC007",
        "ahmedabad": "DC008"
    }

    DC_ZONES = {
        "DC001": "South",
        "DC002": "South",
        "DC003": "South",
        "DC004": "West",
        "DC005": "North",
        "DC006": "East",
        "DC007": "West",
        "DC008": "West"
    }

    def __init__(self):
        self.inventory_service = InventoryService()

    @classmethod
    def set_mode(cls, mode: str):
        if mode in ['AUTO', 'SIMULATED', 'NEWS']:
            cls._active_mode = mode
            logger.info(f"Operational mode switched to {mode}")

    @classmethod
    def get_mode(cls) -> str:
        return cls._active_mode

    @classmethod
    def get_active_scenario(cls, current_date: date) -> dict:
        """
        Retrieves the active scenario based on the operational mode.
        """
        # 1. NEWS MODE
        if cls._active_mode == 'NEWS':
            if cls._news_scenario:
                # Add weather parameters to the extracted news scenario
                sev = cls._news_scenario.get("severity", "Medium").upper()
                temp = 25.0
                rainfall = 0.0
                diseases = []
                event = cls._news_scenario.get("event", "Health Advisory")
                
                if "FLOOD" in event.upper() or "RAIN" in event.upper() or "WATER" in event.upper():
                    rainfall = 150.0 if sev == "CRITICAL" else (100.0 if sev == "HIGH" else 40.0)
                    temp = 24.0
                    diseases = ["Gastroenteritis", "Waterborne Infections (Cholera, Typhoid)", "Dengue Outbreak"]
                elif "HEAT" in event.upper():
                    temp = 43.0 if sev == "CRITICAL" else (40.5 if sev == "HIGH" else 37.0)
                    diseases = ["Dehydration / Heat Exhaustion", "Sunstroke", "Gastrointestinal disorders"]
                elif "DENGUE" in event.upper() or "MOSQUITO" in event.upper():
                    diseases = ["Dengue Fever / Joint pain", "High Fever", "Malaria Outbreak"]
                    temp = 28.0
                    rainfall = 8.0
                else:
                    diseases = ["Viral Infections", "Influenza", "Respiratory distress"]
                    temp = 22.0
                    
                return {
                    "event": event,
                    "region": cls._news_scenario.get("region", "Chennai"),
                    "area": cls._news_scenario.get("area", "Urban limits"),
                    "severity": cls._news_scenario.get("severity", "Medium"),
                    "temperature": temp,
                    "rainfall": rainfall,
                    "season": "AI Extracted News Event",
                    "possible_diseases": diseases,
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "is_simulated": False,
                    "rationale": cls._news_scenario.get("rationale", "Extracted from trending Indian health news.")
                }
            else:
                return {
                    "event": "Pending Live News Analysis",
                    "region": "Chennai",
                    "area": "Local DC",
                    "severity": "Low",
                    "temperature": 26.0,
                    "rainfall": 5.0,
                    "season": "Live News Feed",
                    "possible_diseases": ["Influenza / Seasonal Flu"],
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "is_simulated": False,
                    "rationale": "Press 'Fetch & Analyze News' to process headlines."
                }

        # 2. SIMULATION MODE
        if cls._active_mode == 'SIMULATED' and cls._simulated_event:
            sev = cls._simulated_severity.upper()
            temp = 25.0
            rainfall = 0.0
            diseases = []
            
            if "FLOOD" in cls._simulated_event.upper() or "RAIN" in cls._simulated_event.upper():
                rainfall = 180.0 if sev == "CRITICAL" else (120.0 if sev == "HIGH" else (60.0 if sev == "MEDIUM" else 15.0))
                temp = 24.5
                diseases = ["Waterborne diseases (Cholera, Typhoid)", "Gastroenteritis", "Dengue Outbreak", "Skin Infections"]
            elif "CYCLONE" in cls._simulated_event.upper():
                rainfall = 140.0 if sev == "CRITICAL" or sev == "HIGH" else 45.0
                temp = 25.0
                diseases = ["Wound / Trauma Infections", "Waterborne diseases", "Respiratory issues from wind exposure"]
            elif "HEATWAVE" in cls._simulated_event.upper():
                temp = 44.5 if sev == "CRITICAL" else (42.0 if sev == "HIGH" else (39.0 if sev == "MEDIUM" else 36.0))
                diseases = ["Dehydration / Heat Exhaustion", "Sunstroke", "Gastroenteritis", "Cardiovascular stress"]
            elif "DENGUE" in cls._simulated_event.upper():
                diseases = ["Dengue Fever / Hemorrhagic complications", "High Fever", "Joint / Muscle pains"]
                temp = 28.0
                rainfall = 12.0
            elif "FLU" in cls._simulated_event.upper() or "VIRAL" in cls._simulated_event.upper():
                diseases = ["Influenza (Seasonal Flu)", "Common Cold", "Upper Respiratory Infections", "Bronchitis"]
                temp = 21.0
                rainfall = 2.0
            else:
                diseases = ["General infection flare-up", "Viral Fever", "Waterborne contamination symptoms"]
                
            return {
                "event": cls._simulated_event,
                "region": cls._simulated_region,
                "area": cls._simulated_area,
                "severity": cls._simulated_severity,
                "temperature": temp,
                "rainfall": rainfall,
                "season": "Simulated Environment",
                "possible_diseases": diseases,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "is_simulated": True
            }

        # 3. AUTO MODE (Time-based calendar)
        month = current_date.month
        if month in [6, 7, 8, 9]:
            return {
                "event": "Monsoon Heavy Rainfall Alert",
                "region": "Chennai",
                "area": "Adyar",
                "severity": "Medium",
                "temperature": 27.0,
                "rainfall": 50.0,
                "season": "Monsoon Season (June - September)",
                "possible_diseases": ["Dengue Fever", "Gastroenteritis", "Waterborne Infections", "Skin rashes"],
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "is_simulated": False
            }
        elif month in [4, 5]:
            return {
                "event": "Heatwave Advisory",
                "region": "Delhi",
                "area": "Connaught Place",
                "severity": "High",
                "temperature": 41.5,
                "rainfall": 0.0,
                "season": "Peak Summer Season (April - May)",
                "possible_diseases": ["Dehydration / Heatstroke", "Gastrointestinal disorders", "Cardiovascular strain"],
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "is_simulated": False
            }
        elif month in [11, 12, 1]:
            return {
                "event": "Winter Flu Outbreak Alert",
                "region": "Mumbai",
                "area": "Bandra",
                "severity": "Medium",
                "temperature": 21.0,
                "rainfall": 1.0,
                "season": "Winter Season (November - January)",
                "possible_diseases": ["Influenza (Seasonal Flu)", "Bronchitis & Asthma spikes", "Viral Fever"],
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "is_simulated": False
            }
        else:
            return {
                "event": "Viral Infection Seasonal Peak",
                "region": "Bangalore",
                "area": "Koramangala",
                "severity": "Low",
                "temperature": 25.5,
                "rainfall": 10.0,
                "season": "Transitional Season (Spring/Autumn)",
                "possible_diseases": ["Common Cold / Cough", "Viral Fever", "Allergic Asthma"],
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "is_simulated": False
            }

    @classmethod
    def set_simulation(cls, event: str, region: str, area: str, severity: str):
        cls._simulated_event = event
        cls._simulated_region = region
        cls._simulated_area = area
        cls._simulated_severity = severity
        cls._active_mode = 'SIMULATED'

    @classmethod
    def reset_simulation(cls):
        cls._simulated_event = None
        cls._simulated_region = None
        cls._simulated_area = None
        cls._simulated_severity = None
        cls._active_mode = 'AUTO'

    @classmethod
    def fetch_live_news(cls) -> list:
        logger.info("Fetching trending health/disaster headlines from Google News RSS...")
        url = "https://news.google.com/rss/search?q=health+outbreak+flood+heatwave+dengue+malaria+india&hl=en-IN&gl=IN&ceid=IN:en"
        
        fallback_headlines = [
            {"title": "Heavy rain triggers flooding in Chennai, municipal teams deployed in low lying areas", "link": "https://news.google.com", "pub_date": "Today"},
            {"title": "Dengue cases report steep rise in Bangalore; health department issues alert for Koramangala", "link": "https://news.google.com", "pub_date": "Yesterday"},
            {"title": "Severe heatwave conditions alert issued for Delhi NCR as temperature crosses 42C", "link": "https://news.google.com", "pub_date": "2 days ago"},
            {"title": "Gastroenteritis cases rise in Mumbai suburbs following local drinking water contamination", "link": "https://news.google.com", "pub_date": "3 days ago"},
            {"title": "Viral fever and influenza spike reported across hospitals in Hyderabad", "link": "https://news.google.com", "pub_date": "4 days ago"}
        ]
        
        try:
            res = requests.get(url, timeout=10)
            if res.status_code == 200:
                root = ET.fromstring(res.content)
                articles = []
                for item in root.findall(".//item")[:10]:
                    title = item.find("title").text
                    if " - " in title:
                        title = title.split(" - ")[0]
                    link = item.find("link").text
                    pub_date = item.find("pubDate").text
                    
                    try:
                        dt = datetime.strptime(pub_date, "%a, %d %b %Y %H:%M:%S %Z")
                        pub_date_str = dt.strftime("%b %d, %I:%M %p")
                    except Exception:
                        pub_date_str = pub_date[:16]

                    articles.append({
                        "title": title,
                        "link": link,
                        "pub_date": pub_date_str
                    })
                cls._news_headlines = articles
                return articles
        except Exception as e:
            logger.warning(f"Failed to fetch live RSS news ({e}). Using mock fallback headlines.")
            
        cls._news_headlines = fallback_headlines
        return fallback_headlines

    @classmethod
    def get_fetched_news(cls) -> list:
        if not cls._news_headlines:
            cls.fetch_live_news()
        return cls._news_headlines

    def extract_scenario_from_news(self, db: Session) -> dict:
        headlines = self.get_fetched_news()
        logger.info(f"Extracting scenario from {len(headlines)} headlines using cloud LLM ({settings.OLLAMA_MODEL})...")

        if CloudLLMClient.is_available():
            try:
                news_snippet = "\n".join([f"- {h['title']} ({h['pub_date']})" for h in headlines])
                prompt = (
                    f"You are an AI assistant. Analyze these news headlines about active health outbreaks and weather hazards in India:\n"
                    f"{news_snippet}\n\n"
                    f"Identify the SINGLE most urgent health or weather emergency mentioned in the headlines. "
                    f"Synthesize the details and output a JSON object in this exact format with NO other conversational text:\n"
                    f"{{\n"
                    f"  \"event\": \"Short Event Description (e.g. Dengue Outbreak or Flash Floods)\",\n"
                    f"  \"region\": \"Must be exactly one of: Chennai, Bangalore, Hyderabad, Mumbai, Delhi, Kolkata, Pune, Ahmedabad (pick the most relevant city matched or close to the article's region)\",\n"
                    f"  \"area\": \"Specific locality/sub-area mentioned in the headline (e.g. Koramangala or Velachery. Default to 'Urban centers' if unknown)\",\n"
                    f"  \"severity\": \"Critical or High or Medium or Low\",\n"
                    f"  \"rationale\": \"One sentence summary from the headlines justifying this selection.\"\n"
                    f"}}\n"
                )

                raw = CloudLLMClient.generate(prompt, temperature=0.1)
                parsed = _clean_json_str(raw)
                if parsed:
                    region_val = parsed.get("region", "Chennai").strip()
                    if region_val.lower() not in self.DC_MAPPING:
                        parsed["region"] = "Chennai"

                    type(self)._news_scenario = parsed
                    logger.info(f"AI extracted news scenario: {parsed}")
                    return parsed
            except Exception as e:
                logger.warning(f"Cloud LLM news extraction failed: {e}. Falling back to rule-based parser.")

        logger.info("Executing rule-based news scenario extractor...")
        event = "Seasonal Outbreak"
        region = "Chennai"
        area = "Urban limits"
        severity = "Medium"
        rationale = "General seasonal health alert based on active headlines."
        
        for h in headlines:
            title = h["title"].lower()
            found_city = None
            for city in self.DC_MAPPING.keys():
                if city in title:
                    found_city = city.capitalize()
                    break
            
            found_event = None
            if "flood" in title or "rain" in title:
                found_event = "Flooding & Waterlogging Emergency"
                severity = "High" if "heavy" in title or "disaster" in title or "trigger" in title else "Medium"
            elif "heatwave" in title or "temperature" in title:
                found_event = "Severe Heatwave Outbreak"
                severity = "High"
            elif "dengue" in title:
                found_event = "Dengue Epidemic Spike"
                severity = "High"
            elif "gastro" in title or "water contamination" in title:
                found_event = "Gastroenteritis Outbreak"
                severity = "Medium"
            elif "flu" in title or "viral" in title:
                found_event = "Seasonal Influenza Surge"
                severity = "Medium"
                
            if found_city and found_event:
                event = found_event
                region = found_city
                rationale = f"Detected in headline: '{h['title']}'"
                if "suburb" in title:
                    area = "Outer suburbs"
                elif "koramangala" in title:
                    area = "Koramangala"
                elif "velachery" in title:
                    area = "Velachery"
                elif "bandra" in title:
                    area = "Bandra"
                break
                
        extracted = {
            "event": event,
            "region": region,
            "area": area,
            "severity": severity,
            "rationale": rationale
        }
        type(self)._news_scenario = extracted
        logger.info(f"Fallback extracted news scenario: {extracted}")
        return extracted

    def run_analysis(self, db: Session, current_date: date) -> dict:
        """
        Performs AI surge predictions across all 8 regions. Propagation
        is calculated using spatial zones decay to prevent querying Ollama 8 times.
        """
        if type(self)._active_mode == 'NEWS' and not type(self)._news_scenario:
            self.extract_scenario_from_news(db)
            
        active_sc = self.get_active_scenario(current_date)
        primary_region = active_sc["region"]
        primary_dc_id = self.DC_MAPPING.get(primary_region.lower(), "DC001")
        
        # 1. Fetch SKUs list
        skus = db.query(SKU).all()

        # 2. Check cloud LLM availability
        analysis_mode = "FALLBACK_MOCK"

        # We will retrieve primary SKU category surges
        primary_surges = {}  # sku_id -> {increase_pct, priority, rationale}
        health_risks = []
        general_recs = "Deploy emergency supplies and coordinate distribution with surrounding zones."

        if CloudLLMClient.is_available():
            try:
                # Gather inventory details at primary DC to provide LLM context
                inv_context = []
                for s in skus[:12]:
                    stat = self.inventory_service.get_inventory_status(db, s.sku_id, primary_dc_id, current_date)
                    inv_context.append({
                        "sku_id": s.sku_id,
                        "name": s.name,
                        "category": s.category,
                        "current_stock": stat.get("available_inventory", 0.0),
                        "avg_daily_demand": stat.get("average_daily_demand", 10.0)
                    })

                prompt_data = {
                    "scenario": active_sc["event"],
                    "region": active_sc["region"],
                    "area": active_sc["area"],
                    "severity": active_sc["severity"],
                    "weather": f"Temp: {active_sc['temperature']}C, Rainfall: {active_sc['rainfall']}mm",
                    "season": active_sc["season"],
                    "associated_diseases": active_sc["possible_diseases"],
                    "target_dc_id": primary_dc_id,
                    "inventory_context": inv_context
                }

                prompt = (
                    f"You are a pharmaceutical demand forecasting expert. Analyze the following health disaster scenario:\n"
                    f"{json.dumps(prompt_data, indent=2)}\n\n"
                    f"Predict the surge in demand for the medications in the inventory context. "
                    f"Return a JSON object in this exact format, with NO other text:\n"
                    f"{{\n"
                    f"  \"health_risks\": [\n"
                    f"    {{\"risk_name\": \"Risk Title\", \"probability\": \"High/Medium/Low\", \"description\": \"Short rationale\"}}\n"
                    f"  ],\n"
                    f"  \"sku_impacts\": [\n"
                    f"    {{\"sku_id\": \"MED001\", \"demand_increase_pct\": 75.0, \"priority\": \"Critical/High/Medium/Low\", \"rationale\": \"Why demand increases\"}}\n"
                    f"  ],\n"
                    f"  \"general_recommendations\": \"Short textual summary instructions.\"\n"
                    f"}}\n"
                )

                raw = CloudLLMClient.generate(prompt, temperature=0.2)
                parsed = _clean_json_str(raw)
                if parsed:
                    health_risks = parsed.get("health_risks", [])
                    general_recs = parsed.get("general_recommendations", general_recs)

                    for item in parsed.get("sku_impacts", []):
                        primary_surges[item["sku_id"]] = {
                            "demand_increase_pct": float(item.get("demand_increase_pct", 0.0)),
                            "priority": str(item.get("priority", "LOW")).upper(),
                            "rationale": str(item.get("rationale", ""))
                        }
                    analysis_mode = "CLOUD_LLM"
            except Exception as e:
                logger.warning(f"Cloud LLM run failed: {e}. Reverting to rule engine.")

        # Fallback heuristic surge initialization
        if not primary_surges:
            logger.info("Initializing fallback demand surges for primary region...")
            event = active_sc["event"].lower()
            sev = active_sc["severity"].upper()
            mult = 1.5 if sev == "CRITICAL" else (1.2 if sev == "HIGH" else (0.8 if sev == "MEDIUM" else 0.4))
            
            for s in active_sc["possible_diseases"]:
                health_risks.append({
                    "risk_name": s,
                    "probability": "High" if mult >= 1.0 else ("Medium" if mult >= 0.6 else "Low"),
                    "description": "Elevated hazard levels based on active health threat indices."
                })

            for sku in skus:
                cat = sku.category.lower()
                inc_pct = 0.0
                rationale = "General seasonal stock requirements."
                
                if "flood" in event or "rain" in event:
                    if cat == "gastrointestinal":
                        inc_pct = 150.0 * mult
                        rationale = "Contaminated water triggers severe outbreaks of gastroenteritis and cholera."
                    elif cat == "antibiotic":
                        inc_pct = 120.0 * mult
                        rationale = "Secondary bacterial skin conditions and wound infections require antibiotics."
                    elif cat == "antipyretic":
                        inc_pct = 100.0 * mult
                        rationale = "High fever management in temporary evacuation shelters."
                elif "heatwave" in event:
                    if cat == "vitamin":
                        inc_pct = 130.0 * mult
                        rationale = "Mass rehydration formulas, electrolyte powders, and energy boosters."
                    elif cat == "gastrointestinal":
                        inc_pct = 90.0 * mult
                        rationale = "Temperature-induced food spoilage leads to gastroenteritis spikes."
                elif "dengue" in event or "flu" in event or "viral" in event:
                    if cat == "antipyretic":
                        inc_pct = 160.0 * mult
                        rationale = "Intense epidemic peaks cause paracetamol and antipyretic shortages."
                    elif cat == "analgesic":
                        inc_pct = 110.0 * mult
                        rationale = "Severe viral-induced body and joint aches need analgesics."
                
                priority = "LOW"
                if inc_pct > 120.0:
                    priority = "CRITICAL"
                elif inc_pct > 80.0:
                    priority = "HIGH"
                elif inc_pct > 40.0:
                    priority = "MEDIUM"

                primary_surges[sku.sku_id] = {
                    "demand_increase_pct": round(inc_pct, 1),
                    "priority": priority,
                    "rationale": rationale
                }

        # 3. SPATIAL PROPAGATION: Distribute surges across all 8 regions
        region_recommendations = {}
        
        for region_name, r_dc_id in self.DC_MAPPING.items():
            r_capitalized = region_name.capitalize()
            
            # Determine proximity multiplier
            if r_dc_id == primary_dc_id:
                proximity_multiplier = 1.0
            elif self.DC_ZONES.get(r_dc_id) == self.DC_ZONES.get(primary_dc_id):
                proximity_multiplier = 0.35 # Same geographical zone (e.g. Chennai -> Bangalore)
            else:
                proximity_multiplier = 0.05 # Distant zone
                
            recs_for_region = []
            
            for sku in skus:
                stat = self.inventory_service.get_inventory_status(db, sku.sku_id, r_dc_id, current_date)
                primary_impact = primary_surges.get(sku.sku_id, {"demand_increase_pct": 0.0, "priority": "LOW", "rationale": ""})
                
                local_inc_pct = primary_impact["demand_increase_pct"] * proximity_multiplier
                local_priority = primary_impact["priority"]
                
                # Downgrade priority for lower surges
                if local_inc_pct <= 10.0:
                    local_priority = "LOW"
                elif local_inc_pct <= 40.0:
                    local_priority = "MEDIUM"
                elif local_inc_pct <= 80.0:
                    local_priority = "HIGH"
                    
                local_rationale = primary_impact["rationale"]
                if proximity_multiplier == 0.35:
                    local_rationale = f"[Zone alert] Neighboring zone hazard. Proactive supply buffer applied."
                elif proximity_multiplier == 0.05:
                    local_rationale = f"[Standard] Distant anomaly. Minor baseline safety buffer."
                    
                recs_for_region.append({
                    "sku_id": sku.sku_id,
                    "sku_name": sku.name,
                    "category": sku.category,
                    "current_stock": stat.get("available_inventory", 0.0),
                    "average_daily_demand": stat.get("average_daily_demand", 10.0),
                    "demand_increase_pct": round(local_inc_pct, 1),
                    "priority": local_priority,
                    "rationale": local_rationale
                })
                
            # Resolve shortages and inter-DC transfers specifically for this region
            self._resolve_shortages_and_transfers(db, r_dc_id, r_capitalized, recs_for_region, current_date)
            region_recommendations[r_capitalized] = recs_for_region

        results = {
            "active_scenario": active_sc,
            "health_risks": health_risks,
            "region_recommendations": region_recommendations,
            "general_recommendations": general_recs,
            "analysis_mode": analysis_mode,
            "model_used": settings.OLLAMA_MODEL if analysis_mode == "CLOUD_LLM" else "Deterministic Heuristics Engine"
        }
        
        type(self)._last_analysis_results = results
        return results

    def _resolve_shortages_and_transfers(self, db: Session, target_dc_id: str, target_region: str, recommendations: list, current_date: date):
        for rec in recommendations:
            stock = rec["current_stock"]
            add = rec["average_daily_demand"]
            inc_pct = rec["demand_increase_pct"]
            sku_id = rec["sku_id"]
            
            normal_demand_7d = add * 7.0
            surge_demand_7d = normal_demand_7d * (1.0 + inc_pct / 100.0)
            
            shortage = max(0.0, surge_demand_7d - stock)
            rec["predicted_demand"] = round(surge_demand_7d, 1)
            rec["shortage"] = round(shortage, 1)
            
            if shortage <= 0:
                rec["recommended_action"] = "No action. Inventory levels comfort predicted demand."
                rec["source_dc_id"] = None
                rec["source_dc_name"] = None
                continue

            other_dcs = db.query(DistributionCenter).filter(DistributionCenter.dc_id != target_dc_id).all()
            
            best_source = None
            max_surplus = 0.0
            
            for dc in other_dcs:
                stat = self.inventory_service.get_inventory_status(db, sku_id, dc.dc_id, current_date)
                if not stat:
                    continue
                    
                avail = stat["available_inventory"]
                rop = stat["reorder_point"]
                
                surplus = avail - rop
                if surplus > 10.0:
                    if surplus > max_surplus:
                        max_surplus = surplus
                        best_source = dc
                        
            if best_source and max_surplus > 10.0:
                transfer_qty = min(shortage, max_surplus)
                rec["recommended_action"] = f"Transfer {transfer_qty:.0f} units from {best_source.name}"
                rec["source_dc_id"] = best_source.dc_id
                rec["source_dc_name"] = best_source.name
                
                remaining = shortage - transfer_qty
                if remaining > 10.0:
                    rec["recommended_action"] += f" & Replenish {remaining:.0f} units from supplier"
            else:
                rec["recommended_action"] = f"Replenish {shortage:.0f} units from supplier"
                rec["source_dc_id"] = None
                rec["source_dc_name"] = None

    @classmethod
    def commit_recommendations(cls, db: Session) -> dict:
        if not cls._last_analysis_results:
            return {"status": "error", "message": "No analysis result exists to commit. Run analysis first."}

        results = cls._last_analysis_results
        active_sc = results["active_scenario"]
        
        recs_to_save = []
        transfers_to_save = []
        
        count_recs = 0
        count_transfers = 0
        
        for region_name, recommendations in results["region_recommendations"].items():
            dc_id = cls.DC_MAPPING.get(region_name.lower(), "DC001")
            
            for item in recommendations:
                shortage = item["shortage"]
                if shortage <= 0:
                    continue
                    
                sku_id = item["sku_id"]
                action = item["recommended_action"]
                priority = item["priority"]
                rationale = item["rationale"]
                
                rec_id = f"REC-AI-{uuid.uuid4().hex[:6].upper()}"
                action_type = "REPLENISH"
                qty = shortage
                
                if item["source_dc_id"]:
                    action_type = "TRANSFER"
                    if "Transfer" in action and "units" in action:
                        try:
                            qty = float(action.split("units")[0].split("Transfer")[1].strip())
                        except Exception:
                            qty = shortage

                rec_obj = Recommendation(
                    recommendation_id=rec_id,
                    timestamp=datetime.utcnow(),
                    sku_id=sku_id,
                    dc_id=dc_id,
                    action_type=action_type,
                    quantity=float(qty),
                    priority=priority,
                    reason=f"[Live AI {region_name} Forecast] {rationale} Action recommended: {action}",
                    expected_impact=f"Resolve regional supply shortage during {active_sc['event']}.",
                    confidence=0.95,
                    status="PENDING"
                )
                recs_to_save.append(rec_obj)
                count_recs += 1
                
                if action_type == "TRANSFER" and item["source_dc_id"]:
                    from app.models.database_models import Batch
                    batch = db.query(Batch).filter(
                        Batch.sku_id == sku_id,
                        Batch.dc_id == item["source_dc_id"],
                        Batch.remaining_quantity >= qty
                    ).order_by(Batch.expiry_date.asc()).first()
                    
                    batch_id = batch.batch_id if batch else "B_TEMP_AI"
                    
                    tr_id = f"TR-AI-{uuid.uuid4().hex[:6].upper()}"
                    tr_obj = Transfer(
                        transfer_id=tr_id,
                        recommendation_id=rec_id,
                        sku_id=sku_id,
                        source_dc_id=item["source_dc_id"],
                        destination_dc_id=dc_id,
                        batch_id=batch_id,
                        quantity=float(qty),
                        transit_days=2,
                        status="RECOMMENDED"
                    )
                    transfers_to_save.append(tr_obj)
                    count_transfers += 1
                    
                    if "& Replenish" in action:
                        try:
                            repl_qty = float(action.split("& Replenish")[1].split("units")[0].strip())
                            rec_id_repl = f"REC-AI-{uuid.uuid4().hex[:6].upper()}"
                            rec_obj_repl = Recommendation(
                                recommendation_id=rec_id_repl,
                                timestamp=datetime.utcnow(),
                                sku_id=sku_id,
                                dc_id=dc_id,
                                action_type="REPLENISH",
                                quantity=float(repl_qty),
                                priority=priority,
                                reason=f"[Live AI {region_name} Forecast] Supplementary order for remaining shortage.",
                                expected_impact=f"Supplemental buy for emergency {active_sc['event']}.",
                                confidence=0.95,
                                status="PENDING"
                            )
                            recs_to_save.append(rec_obj_repl)
                            count_recs += 1
                        except Exception:
                            pass
                            
        if recs_to_save:
            db.bulk_save_objects(recs_to_save)
        if transfers_to_save:
            db.bulk_save_objects(transfers_to_save)
            
        db.commit()
        cls._last_analysis_results = None
        
        return {
            "status": "success",
            "message": f"Successfully committed {count_recs} regional recommendations and {count_transfers} transfers globally!"
        }
