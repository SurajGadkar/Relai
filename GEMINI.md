# Relai AI Engineering & Integration Specification

## 1. System Architecture Overview
Relai is a context-aware recommendation engine. The AI must function as a middleware that synthesizes data from the `Wardrobe Database`, `Weather Service`, and `User Calendar` to output structured JSON for the frontend.

## 2. Technical Integration Ruless

### A. Data Injection Protocol
Before processing a user request, the system must inject the following state:
- **Temporal State:** `ISO-8601 Timestamp`
- **Environmental State:** `Temperature (C/F)`, `Precipitation %`, `Wind Speed`
- **Contextual State:** `Event Category` (e.g., Wedding, Gym, Office), `Formality Level (1-10)`
- **Inventory State:** `List<Item>` where `status != "laundry"`

### B. Output Constraints (Strict JSON)
The AI must strictly adhere to the following schema to prevent frontend parsing errors:
```json
{
  "outfit_id": "UUID",
  "metadata": {
    "generated_at": "Timestamp",
    "engine_version": "v1.2"
  },
  "recommendation": {
    "outfit_name": "String",
    "confidence_score": "Float",
    "rationale": "String",
    "items": {
      "base_layer": "ItemID",
      "mid_layer": "ItemID | null",
      "outerwear": "ItemID | null",
      "bottom": "ItemID",
      "footwear": "ItemID",
      "accessories": ["ItemID"]
    }
  }
}
```

## 3. Software Engineering Principles

### 1. Deterministic Fallbacks
- **API Timeout:** If the LLM fails to respond within 2000ms, the system must fallback to a "Heuristic-Based Template" (e.g., Season-appropriate basics).
- **Token Optimization:** Use `ItemID` references instead of full object descriptions in the prompt to minimize context window usage.

### 2. State Management
- **Laundry Logic:** The AI must never suggest an item where `is_available == false`.
- **Rotation Logic:** Implement a "Recency Penalty." If an item was suggested and accepted in the last 48 hours, reduce its weight in the selection algorithm to ensure wardrobe variety.

### 3. Error Handling
- **Incomplete Wardrobe:** If the user lacks a critical layer (e.g., no coat for -5°C), the AI must return a `warning` flag in the JSON and suggest the closest alternative with a "Gap Analysis" note.

## 4. Prompt Engineering Strategy

- **Few-Shot Prompting:** Provide the model with 3 examples of "Perfect Matches" (e.g., Rainy Day + Business Meeting).
- **Chain-of-Thought (CoT):** Force the model to reason through the weather requirements before selecting items.
- **Negative Constraints:** 
    - "Do not suggest open-toed shoes if precipitation > 30%."
    - "Do not suggest shorts for 'Professional' formality events."

## 5. Performance Metrics (KPIs)
- **Latency:** < 2.0s (End-to-End).
- **Accuracy:** > 90% alignment with user-defined style archetypes.
- **Utility:** Increase in "Wardrobe Utilization Rate" (Items worn vs. Items owned).

---
*Document Version: 1.0.0 | Relai Engineering Team*