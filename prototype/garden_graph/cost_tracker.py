"""
Cost Tracker - tracks token usage and estimated USD cost for all LLM calls.
"""
from typing import Dict, List, Tuple, Any
from datetime import datetime
import json
import os

# Import configuration
from garden_graph.config import DISABLE_COST_TRACKING, BUDGET_LIMIT

# Default pricing per 1K tokens (can be updated)
DEFAULT_PRICING = {
    "gpt-3.5-turbo": {"prompt": 0.0015, "completion": 0.002},
    "gpt-4": {"prompt": 0.03, "completion": 0.06},
    "gpt-4-turbo": {"prompt": 0.01, "completion": 0.03},
    "gpt-4.1-turbo": {"prompt": 0.01, "completion": 0.03},
    # Approximate pricing for GPT-4o (update if OpenAI publishes changes)
    "gpt-4o": {"prompt": 0.005, "completion": 0.015},
    "claude-instant-1": {"prompt": 0.0008, "completion": 0.0024},
    "claude-2": {"prompt": 0.011, "completion": 0.032},
    "claude-3-sonnet": {"prompt": 0.008, "completion": 0.024}
}

class CostRecord:
    """Record of a single LLM call with tokens and cost."""
    
    def __init__(self, 
                 model_id: str, 
                 prompt_tokens: int, 
                 completion_tokens: int,
                 message_id: str = None):
        """Initialize with model ID and token counts."""
        self.id = f"cost_{datetime.now().timestamp()}"
        self.model_id = model_id
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.message_id = message_id
        self.created_at = datetime.now()
        
        # Calculate USD cost
        pricing = DEFAULT_PRICING.get(model_id, {"prompt": 0, "completion": 0})
        self.usd = (
            (prompt_tokens / 1000) * pricing["prompt"] + 
            (completion_tokens / 1000) * pricing["completion"]
        )
        
    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "model_id": self.model_id,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "usd": self.usd,
            "created_at": self.created_at.isoformat(),
            "message_id": self.message_id
        }


class CostTracker:
    """Tracks token usage and cost across all LLM calls."""
    
    def __init__(self):
        """Initialize cost tracker."""
        self.records = []
        self.session_usd = 0.0
        self.budget_limit = BUDGET_LIMIT  # Use configured limit
        self.disabled = DISABLE_COST_TRACKING
        
    def record(self, 
               model: str, 
               prompt_tokens: int, 
               completion_tokens: int,
               message_id: str = None) -> CostRecord:
        """Record a new LLM call and update totals."""
        # Skip if cost tracking is disabled
        if self.disabled:
            return CostRecord(model, 0, 0, message_id)  # Return empty record
            
        record = CostRecord(model, prompt_tokens, completion_tokens, message_id)
        self.records.append(record)
        
        # Update session total
        self.session_usd += record.usd
        
        # Check if over budget
        if self.budget_limit > 0 and self.session_usd > self.budget_limit:
            print(f"⚠️ WARNING: Budget limit of ${self.budget_limit:.2f} exceeded. Current cost: ${self.session_usd:.2f}")
            
        return record
    
    def get_total_usd(self) -> float:
        """Get total USD spent in this session."""
        return self.session_usd
    
    def get_model_breakdown(self) -> Dict[str, float]:
        """Get breakdown of cost by model."""
        result = {}
        for record in self.records:
            model = record.model_id
            if model not in result:
                result[model] = 0
            result[model] += record.usd
        return result
    
    def export_csv(self, file_path: str) -> None:
        """Export all records to CSV."""
        import csv
        with open(file_path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                "ID", "Model", "Prompt Tokens", "Completion Tokens", 
                "USD", "Created At", "Message ID"
            ])
            for record in self.records:
                d = record.to_dict()
                writer.writerow([
                    d["id"], d["model_id"], d["prompt_tokens"], 
                    d["completion_tokens"], d["usd"], 
                    d["created_at"], d["message_id"] or ""
                ])
                
    def set_budget_limit(self, limit: float) -> None:
        """Set monthly budget limit in USD."""
        self.budget_limit = limit
        
    def reset(self) -> None:
        """Reset all records and totals."""
        self.records = []
        self.session_usd = 0.0
