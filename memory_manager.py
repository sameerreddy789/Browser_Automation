from loguru import logger
from mem0 import Memory

class MemoryManager:
    """
    Manages long-term graph-based and vector-based memory for the agent using Mem0.
    Replaces the static agent_memory.json file.
    """
    def __init__(self, user_id: str = "agent_default"):
        self.user_id = user_id
        
        # Configure Mem0 to use local storage.
        config = {
            "vector_store": {
                "provider": "chroma",
                "config": {
                    "collection_name": "agent_memory",
                    "path": "./agent_mem0_db"
                }
            }
        }
        
        try:
            self.memory = Memory.from_config(config_dict=config)
            logger.info("✅ [MEM0]: Memory engine initialized successfully.")
        except Exception as e:
            logger.warning(f"⚠️ [MEM0]: Failed to initialize Memory engine: {e}")
            self.memory = None

    def store_knowledge(self, site: str, observation: str):
        """Store a successful workaround or site observation."""
        if not self.memory:
            return
            
        data = f"Site: {site} | Observation: {observation}"
        try:
            self.memory.add(data, user_id=self.user_id, metadata={"site": site, "type": "workaround"})
            logger.info(f"✅ [MEM0]: Stored knowledge for {site}")
        except Exception as e:
            logger.error(f"❌ [MEM0]: Error storing knowledge: {e}")

    def get_relevant_knowledge(self, site: str) -> str:
        """Retrieve relevant knowledge for a specific site."""
        if not self.memory:
            return ""
            
        try:
            results = self.memory.search(f"How do I interact with {site}?", user_id=self.user_id)
            if not results:
                return ""
                
            knowledge_items = [res.get("memory", "") for res in results]
            combined = "\n- ".join(knowledge_items)
            return f"\n- {combined}" if combined else ""
        except Exception as e:
            logger.error(f"❌ [MEM0]: Error retrieving knowledge: {e}")
            return ""

# Singleton instance
memory_manager = MemoryManager()
