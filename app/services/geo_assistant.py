from __future__ import annotations

import re

ALLOWED_INTENTS={
 "citoyen":{"report_status","next_collection","collection_state","nearby_drop_points","open_resource"},
 "agent":{"assigned_interventions","nearest_intervention","interventions_in_zone","open_resource"},
 "ramasseur":{"next_collection","remaining_stops","show_route","report_incident","open_resource"},
 "admin":{"unassigned_collections","late_tours","open_incidents","reports_in_zone","resources_requiring_action"},
 "gestionnaire":{"unassigned_collections","late_tours","open_incidents","reports_in_zone","resources_requiring_action"},
 "municipal":{"unassigned_collections","late_tours","open_incidents","reports_in_zone","resources_requiring_action"},
}

BLOCKED_PATTERNS=(r"\b(select|insert|update|delete|drop|alter|union)\b",r"ignore (les |toutes les |all )?instructions",r"token|password|mot de passe|secret",r"autre utilisateur|another user",r"/api/|https?://")

KEYWORDS={
 "report_status":("statut signalement","report status","où se trouve mon signalement"),
 "next_collection":("prochaine collecte","next collection"),
 "collection_state":("collecte en route","collection on the way"),
 "nearby_drop_points":("points de dépôt","drop points","point de collecte proche"),
 "assigned_interventions":("interventions affectées","assigned interventions"),
 "nearest_intervention":("intervention la plus proche","nearest intervention"),
 "interventions_in_zone":("interventions dans ma zone","interventions in my area"),
 "remaining_stops":("arrêts restent","remaining stops"),
 "show_route":("afficher mon itinéraire","show my route","mon itinéraire"),
 "report_incident":("signaler un problème","report a problem"),
 "unassigned_collections":("collectes non affectées","unassigned collections"),
 "late_tours":("tournées en retard","late tours"),
 "open_incidents":("incidents ouverts","open incidents"),
 "reports_in_zone":("signalements dans une zone","reports in area"),
 "resources_requiring_action":("nécessitent une action","require action"),
 "open_resource":("ouvrir ma ressource","open my resource"),
}

def identify_intent(text:str,role:str,explicit:str|None=None)->str:
    normalized=" ".join((text or "").lower().split())[:500]
    if any(re.search(pattern,normalized,re.IGNORECASE) for pattern in BLOCKED_PATTERNS):raise ValueError("Instruction non autorisée")
    intent=explicit
    if not intent:
        matches=[name for name,keywords in KEYWORDS.items() if any(keyword in normalized for keyword in keywords)]
        if len(matches)!=1:raise LookupError("Précisez votre demande géographique")
        intent=matches[0]
    if intent not in ALLOWED_INTENTS.get(role,set()):raise PermissionError("Intention non autorisée pour ce rôle")
    return intent

def response(language:str,message_fr:str,message_en:str,*,facts=None,link=None,needs_clarification=False):
    return {"language":"en" if language=="en" else "fr","message":message_en if language=="en" else message_fr,"facts":facts or {},"link":link,"needs_clarification":needs_clarification,"source":"authorized_server_data"}
