import json
from typing import Any, Callable
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from app.llm.models import PreferenceExtraction
from app.llm.state import AgentState
from app.llm.prompts import USER_INPUT_PROMPT, RESPONSE_GENERATION_PROMPT


# --------------------------------------------------
# Preference extraction node
# --------------------------------------------------

def build_preference_extraction_node(llm):

    structured_llm = llm.with_structured_output(PreferenceExtraction)

    def extract_preferences(state: AgentState) -> dict[str, Any]:

        user_query = state.get("user_query", "")

        if not user_query.strip():
            return {}

        result = structured_llm.invoke([
            SystemMessage(content=USER_INPUT_PROMPT),
            HumanMessage(content=user_query),
        ])

        # Preserve existing values when the latest message
        # does not provide new information.
        dietary = (
            result.dietary_preference
            if result.dietary_preference is not None
            else state.get("dietary_preference")
        )

        allergy_status = state.get("allergy_status", "unknown")

        if result.allergy_status not in (None, "unknown"):
            allergy_status = result.allergy_status
            allergens = state.get("allergens", [])

        if result.allergens is not None:
            allergens = result.allergens

        # If the customer explicitly says they have no allergies,
        # clear previously stored allergen information.
        if allergy_status == "none":
            allergens = []

        # Do not proceed if the customer says they have allergies
        # but has not specified which ones.
        preferences_complete = (
            dietary is not None
            and allergy_status != "unknown"
            and (
                allergy_status == "none"
                or bool(allergens)
            )
        )

        return {
            "dietary_preference": dietary,
            "allergy_status": allergy_status,
            "allergens": allergens,
            "preferences_complete": preferences_complete,
        }

    return extract_preferences


# --------------------------------------------------
# Clarification node
# --------------------------------------------------

def ask_clarification(state: AgentState) -> dict[str, Any]:

    questions = []

    if state.get("dietary_preference") is None:
        questions.append(
            "Do you prefer vegetarian, non-vegetarian, egg-based food, or do you have no preference?"
        )

    allergy_status = state.get("allergy_status", "unknown")
    allergens = state.get("allergens", [])

    if allergy_status == "unknown":
        questions.append(
            "Do you have any food allergies? "
        )

    elif allergy_status == "has_allergies" and not allergens:
        questions.append(
            "Which specific food allergies should I consider?"
        )

    response = " ".join(questions)

    return {
        "response": response,
        "messages": [AIMessage(content=response)],
    }


# --------------------------------------------------
# Menu retrieval node
# --------------------------------------------------

def build_retrieval_node(
    retrieval_fn: Callable[
        [str, str, list[str], str],
        list[dict],
    ],
):

    def retrieve_menu(state: AgentState) -> dict[str, Any]:

        if not state.get("preferences_complete", False):
            raise ValueError(
                "Cannot retrieve menu items before preferences are complete."
            )

        items = retrieval_fn(
            state["dietary_preference"],
            state["allergy_status"],
            state.get("allergens", []),
            state.get("user_query", ""),
        )

        return {
            "retrieved_items": items,
        }

    return retrieve_menu


# --------------------------------------------------
# Response generation node
# --------------------------------------------------

def build_response_generation_node(llm):

    def generate_response(state: AgentState) -> dict[str, Any]:

        menu_context = json.dumps(
            state.get("retrieved_items", []),
            ensure_ascii=False,
            default=str,
        )

        user_query = state.get("user_query", "")

        response = llm.invoke([
            SystemMessage(content=RESPONSE_GENERATION_PROMPT),
            HumanMessage(
                content=(
                    f"Customer query:\n{user_query}\n\n"
                    f"Retrieved menu items:\n{menu_context}\n\n"
                    f"Dietary preference: "
                    f"{state.get('dietary_preference')}\n"
                    f"Allergy status: "
                    f"{state.get('allergy_status')}\n"
                    f"Allergens: "
                    f"{state.get('allergens', [])}"
                )
            ),
        ])

        response_text = response.content

        if not isinstance(response_text, str):
            response_text = str(response_text)

        return {
            "response": response_text,
            "messages": [AIMessage(content=response_text)],
        }

    return generate_response
