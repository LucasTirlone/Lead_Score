# src/api/normalize_leads.py
from typing import Any, Dict, List

def normalize_batch(payload: Any) -> Dict[str, List[Dict[str, Any]]]:
    """
    Mínimo necessário: aceita objeto único, lista, ou {"leads":[...]} e devolve {"leads":[...]}.
    (Não faz mais transformação; o LLM cuida da extração/score.)
    """
    if isinstance(payload, dict) and "leads" in payload and isinstance(payload["leads"], list):
        leads = payload["leads"]
    elif isinstance(payload, list):
        leads = payload
    elif isinstance(payload, dict):
        leads = [payload]
    else:
        leads = []
    return {"leads": leads}
