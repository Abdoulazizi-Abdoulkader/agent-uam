"""
Gestion de la mémoire à long terme pour les préférences utilisateur
"""
import os
import json
from typing import Dict, Any, List
from datetime import datetime


class UserMemory:
    """Gestion de la mémoire à long terme pour les préférences utilisateur"""

    def __init__(self, memory_file: str = "user_memory.json"):
        self.memory_file = memory_file
        self.memory = self._load_memory()

    def _load_memory(self) -> Dict[str, Any]:
        """Charge la mémoire depuis le fichier JSON"""
        if os.path.exists(self.memory_file):
            try:
                with open(self.memory_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f" Erreur lors du chargement de la mémoire: {e}")
                return {}
        return {}

    def _save_memory(self):
        """Sauvegarde la mémoire dans le fichier JSON"""
        try:
            with open(self.memory_file, 'w', encoding='utf-8') as f:
                json.dump(self.memory, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f" Erreur lors de la sauvegarde de la mémoire: {e}")

    def get_user_preferences(self, user_id: str) -> Dict[str, Any]:
        """Récupère les préférences d'un utilisateur"""
        if user_id not in self.memory:
            self.memory[user_id] = {
                "preferences": {},
                "conversation_history": [],
                "created_at": datetime.now().isoformat(),
                "last_updated": datetime.now().isoformat()
            }
        return self.memory[user_id].get("preferences", {})

    def save_user_preference(self, user_id: str, key: str, value: Any):
        """Sauvegarde une préférence utilisateur"""
        if user_id not in self.memory:
            self.memory[user_id] = {
                "preferences": {},
                "conversation_history": [],
                "created_at": datetime.now().isoformat(),
                "last_updated": datetime.now().isoformat()
            }

        self.memory[user_id]["preferences"][key] = value
        self.memory[user_id]["last_updated"] = datetime.now().isoformat()
        self._save_memory()

    def add_conversation(self, user_id: str, question: str, response: str):
        """Ajoute une conversation à l'historique"""
        if user_id not in self.memory:
            self.memory[user_id] = {
                "preferences": {},
                "conversation_history": [],
                "created_at": datetime.now().isoformat(),
                "last_updated": datetime.now().isoformat()
            }

        self.memory[user_id]["conversation_history"].append({
            "question": question,
            "response": response,
            "timestamp": datetime.now().isoformat()
        })
        self.memory[user_id]["last_updated"] = datetime.now().isoformat()
        self._save_memory()
    
    def get_conversation_history(self, user_id: str, limit: int = 10) -> List[Dict]:
        """Récupère l'historique des conversations"""
        if user_id not in self.memory:
            return []
        return self.memory[user_id].get("conversation_history", [])[-limit:]


# Instance globale de la mémoire
_user_memory = UserMemory()

