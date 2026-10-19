"""
RideNow AI — Knowledge & Policies Tool
======================================
Allows the AI assistant to consult official RideNow policy documents,
FAQs, safety protocols, and driver guides via RAG.
"""

from typing import Dict, Any


async def search_policies_and_faq_tool(query: str, **kwargs) -> Dict[str, Any]:
    """
    Search the RideNow knowledge base for official policies, FAQs, fare rules,
    cancellation rules, safety protocols, and driver instructions.
    
    Args:
        query: Specific question or search phrase.
    """
    from app.ai.rag.retriever import retrieve_relevant_knowledge, format_knowledge_context

    snippets = retrieve_relevant_knowledge(query, top_k=3)
    if not snippets:
        return {
            "success": False,
            "message": "No matching policy or guideline found for this query.",
            "results": [],
        }

    formatted = format_knowledge_context(snippets)
    return {
        "success": True,
        "results_count": len(snippets),
        "context": formatted,
    }
