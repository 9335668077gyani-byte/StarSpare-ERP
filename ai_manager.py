import re
import random
import json
import urllib.request
from PyQt6.QtCore import QThread, pyqtSignal
from logger import app_logger
from difflib import SequenceMatcher

class OllamaWorker(QThread):
    chunk_received = pyqtSignal(str)
    finished_signal = pyqtSignal()
    error_signal = pyqtSignal(str)

    def __init__(self, prompt, parent=None):
        super().__init__(parent)
        self.prompt = prompt

    def run(self):
        url = "http://localhost:11434/api/generate"
        data = json.dumps({
            "model": "llama3", 
            "prompt": self.prompt,
            "stream": True
        }).encode('utf-8')
        req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(req) as response:
                for line in response:
                    if line:
                        chunk = json.loads(line)
                        if 'response' in chunk:
                            self.chunk_received.emit(chunk['response'])
                        if chunk.get('done'):
                            break
            self.finished_signal.emit()
        except Exception as e:
            self.error_signal.emit(str(e))

class AIAssistant:
    def __init__(self, db_manager):
        self.db = db_manager
        self._cache_keywords()
        
    def _cache_keywords(self):
        """
        Cache common vehicle models and part names from database for intelligent matching.
        """
        try:
            all_parts = self.db.get_all_parts()
            
            # Extract unique vehicle models from descriptions and compatibility fields
            self.vehicle_models = set()
            self.part_keywords = set()
            
            for part in all_parts:
                # part structure: 0=id, 1=name, 2=description, 9=compatibility
                desc = str(part[2]).upper() if part[2] else ""
                compat = str(part[9]).upper() if len(part) > 9 and part[9] else ""
                part_name = str(part[1]).upper() if part[1] else ""
                
                # Extract vehicle models (common patterns)
                # Examples: "APACHE RTR 160", "RONIN", "RADEON", "RAIDER 125"
                models = re.findall(r'\b([A-Z]+(?:\s+[A-Z0-9]+)*)\b', desc + " " + compat)
                self.vehicle_models.update(models)
                
                # Extract part keywords from part names
                # Examples: "BRAKE", "FILTER", "GASKET", "KIT"
                keywords = re.findall(r'\b([A-Z]{3,})\b', part_name)
                self.part_keywords.update(keywords)
                
            app_logger.info(f"AI Cache: {len(self.vehicle_models)} vehicle models, {len(self.part_keywords)} part keywords")
        except Exception as e:
            app_logger.error(f"Failed to cache keywords: {e}")
            self.vehicle_models = set()
            self.part_keywords = set()
    
    def _fuzzy_match(self, query, candidates, threshold=0.6):
        """
        Find best matching candidate using fuzzy string matching.
        Returns (best_match, score) or (None, 0) if no good match.
        """
        query = query.upper()
        best_match = None
        best_score = 0
        
        for candidate in candidates:
            # Calculate similarity ratio
            ratio = SequenceMatcher(None, query, candidate).ratio()
            
            # Also check if query is substring of candidate
            if query in candidate:
                ratio = max(ratio, 0.8)
            
            if ratio > best_score and ratio >= threshold:
                best_score = ratio
                best_match = candidate
                
        return best_match, best_score
    
    def _extract_vehicle_model(self, text):
        """
        Intelligently extract vehicle model from user query using database knowledge.
        """
        text_upper = text.upper()
        
        # Try exact match first
        for model in self.vehicle_models:
            if model in text_upper:
                return model
        
        # Try fuzzy matching
        # Extract potential model name from query
        patterns = [
            r'(?:for|fits|model)\s+(?P<model>[\w\s\d]+)',
            r'(?:parts|spares)\s+(?:for|of)\s+(?P<model>[\w\s\d]+)',
            r'\b(?P<model>[A-Z]{3,}(?:\s+[A-Z0-9]+)*)\b'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text_upper)
            if match:
                query_model = match.group('model').strip()
                best_match, score = self._fuzzy_match(query_model, self.vehicle_models, threshold=0.5)
                if best_match:
                    app_logger.info(f"Fuzzy matched '{query_model}' to '{best_match}' (score: {score:.2f})")
                    return best_match
        
        return None
    
    def _extract_part_keyword(self, text):
        """
        Extract part keyword from user query using database knowledge.
        """
        text_upper = text.upper()
        
        # Try exact match first
        for keyword in self.part_keywords:
            if keyword in text_upper:
                return keyword
        
        # Try fuzzy matching
        words = re.findall(r'\b([A-Z]{3,})\b', text_upper)
        for word in words:
            best_match, score = self._fuzzy_match(word, self.part_keywords, threshold=0.6)
            if best_match:
                app_logger.info(f"Fuzzy matched part '{word}' to '{best_match}' (score: {score:.2f})")
                return best_match
        
        return None
        
    def process_query(self, text):
        """
        Intelligently parses user text using database knowledge and returns formatted response.
        """
        text_clean = text.lower().strip()
        app_logger.info(f"AI Query: {text}")
        
        # 1. Greetings
        if re.search(r'\b(hello|hi|hey|namaste|greetings)\b', text_clean):
            return "NAMASTE! How can I help you?"
        
        # 2. Compatibility Queries - "Parts for X", "X parts", "fits X"
        if any(keyword in text_clean for keyword in ["parts", "for", "fits", "compatible", "spares"]):
            model = self._extract_vehicle_model(text)
            if model:
                return self._handle_compatibility(model)
            else:
                match = re.search(r'(?:for|fits|of)\s+(?P<term>[\w\s]+)', text_clean)
                if match:
                    term = match.group('term').strip()
                    return self._handle_compatibility(term)
        
        # 3. Price Queries - "Price of X"
        if any(keyword in text_clean for keyword in ["price", "cost", "rate"]):
            match = re.search(r'(?:price|cost|rate)\s+(?:of\s+|is\s+)?(?P<part>[\w\s\d]+)', text_clean)
            if match:
                part_name = match.group('part').strip()
                keyword = self._extract_part_keyword(part_name)
                search_term = keyword if keyword else part_name
                return self._handle_price_lookup(search_term)
        
        # 4. Stock Queries - "Stock of X"
        if any(keyword in text_clean for keyword in ["stock", "available", "qty"]):
            match = re.search(r'(?:stock|available|qty)\s+(?:of\s+)?(?P<part>[\w\s\d]+)', text_clean)
            if match:
                part_name = match.group('part').strip()
                keyword = self._extract_part_keyword(part_name)
                search_term = keyword if keyword else part_name
                return self._handle_stock_lookup(search_term)
        
        # 5. General Search fallback
        return self._handle_compatibility(text_clean)

    def _handle_compatibility(self, model):
        """Search for parts compatible with a vehicle model."""
        results = self.db.search_by_compatibility(model)
        
        if not results:
            return f"No parts found for '{model}'."
            
        resp = f"Found {len(results)} parts for '{model.upper()}':\n"
        for i, row in enumerate(results[:5], 1):
            # row: 0=id, 1=name, 2=desc, 3=price, 4=qty, 5=rack
            name = row[1]
            price = row[3]
            rack = row[5]
            # Format: "1. Brake Pad (Rack 2) - ₹250"
            resp += f"{i}. {name} (Rack {rack}) - ₹{price}\n"
            
        if len(results) > 5:
            resp += f"...and {len(results)-5} more."
            
        return resp

    def _handle_price_lookup(self, part_name):
        """Look up price for a specific part."""
        results = self.db.search_by_compatibility(part_name)
        
        if not results:
            return f"Part '{part_name}' not found."
            
        resp = f"Price check for '{part_name.upper()}':\n"
        for i, row in enumerate(results[:3], 1):
            name = row[1]
            price = row[3]
            resp += f"{i}. {name} - ₹{price}\n"
            
        return resp

    def _handle_stock_lookup(self, part_name):
        """Check stock availability for a part."""
        results = self.db.search_by_compatibility(part_name)
        
        if not results:
            return f"Part '{part_name}' not found."
            
        resp = f"Stock check for '{part_name.upper()}':\n"
        for i, row in enumerate(results[:3], 1):
            name = row[1]
            qty = row[4]
            rack = row[5]
            status = "IN STOCK" if qty > 0 else "OUT OF STOCK"
            resp += f"{i}. {name} (Rack {rack}): {qty} units [{status}]\n"
            
        return resp
    
    def _handle_general_search(self, keyword):
        return self._handle_compatibility(keyword)

    def parse_expense_command(self, text):
        """
        Parses a natural language expense command using regex and keyword mapping.
        Format: "Item Amount" -> e.g., "Tea 20", "Petrol 500"
        """
        try:
            from datetime import datetime
            text = text.strip()
            
            # 1. key extraction: Find the number strings
            # Look for amount (supports integers and decimals)
            match_amount = re.search(r'(\d+(\.\d+)?)', text)
            if not match_amount:
                return None, "Could not identify an amount. Try 'Tea 20'."
                
            amount_str = match_amount.group(1)
            amount = float(amount_str)
            
            # 2. Extract Title
            # Remove the amount from the string to identify the item
            # Also remove common filler words
            title = text.replace(amount_str, "")
            title = re.sub(r'\b(rs|rupees|inr|cost|paid|for)\b', '', title, flags=re.IGNORECASE).strip()
            
            # Remove extra spaces/punctuation
            title = re.sub(r'[^\w\s]', '', title).strip()
            
            # Default title if empty
            if not title:
                title = "Miscellaneous Expense"
                
            # 3. Auto-Categorize based on keywords
            category = "Miscellaneous"
            title_lower = title.lower()
            
            cat_map = {
                "Refreshment": ["tea", "coffee", "chai", "snacks", "biscuit", "lunch", "dinner", "water", "food"],
                "Transport": ["petrol", "fuel", "diesel", "auto", "taxi", "bus", "travel", "transport"],
                "Utility": ["bill", "light", "electricity", "power", "internet", "wifi", "recharge", "phone"],
                "Salary": ["salary", "wages", "staff", "advance"],
                "Rent/Fixed": ["rent", "shop", "maintenance", "tax"],
                "Inventory": ["parts", "purchase", "stock", "delivery", "courier"]
            }
            
            for cat, keywords in cat_map.items():
                if any(k in title_lower for k in keywords):
                    category = cat
                    break
            
            return {
                "title": title.title(),
                "amount": amount,
                "category": category,
                "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }, None
            
        except Exception as e:
            app_logger.error(f"AI Parse Error: {e}")
            return None, "AI Processing Error."
