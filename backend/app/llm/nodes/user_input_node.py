import json
from typing import Any, Callable
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from app.llm.models import UserInputAnalysis
from app.llm.state import AgentState
from app.llm.prompts import USER_INPUT_PROMPT, RESPONSE_GENERATION_PROMPT

# --------------------------------------------------
# User input understanding node
# --------------------------------------------------

def build_user_input_node(llm):

    structured_llm = llm.with_structured_output(UserInputAnalysis)

    def process_user_input(state: AgentState) -> dict[str, Any]:

        user_query = state.get("user_query", "").strip()
        if not user_query:
            return {}

        # Extract intent and preferences from the latest message.
        result = structured_llm.invoke([
            SystemMessage(content=USER_INPUT_PROMPT),
            HumanMessage(content=user_query),
        ])

        # Preserve existing dietary preference unless updated.
        dietary = (
            result.dietary_preference
            if result.dietary_preference is not None
            else state.get("dietary_preference")
        )

        # Preserve existing allergy information unless explicitly updated.
        allergy_status = state.get("allergy_status", "unknown")
        allergens = state.get("allergens", [])

        if result.allergy_status == "none":
            allergy_status = "none"
            allergens = []

        elif result.allergy_status == "has_allergies":
            allergy_status = "has_allergies"

            if result.allergens is not None:
                allergens = list(
                    dict.fromkeys(allergens + result.allergens)
                )

        elif result.allergy_status == "unknown":
            # Unknown in the latest extraction does not erase
            # previously collected allergy information.
            pass

        # Both dietary preference and allergy information
        # must be known before menu retrieval.
        preferences_complete = (
            dietary is not None
            and (
                allergy_status == "none"
                or (
                    allergy_status == "has_allergies"
                    and bool(allergens)
                )
            )
        )

        return {
            "intent": result.intent,
            "dietary_preference": dietary,
            "allergy_status": allergy_status,
            "allergens": allergens,
            "preferences_complete": preferences_complete,
        }

    return process_user_input


# --------------------------------------------------
# Clarification node
# --------------------------------------------------

def ask_clarification(state: AgentState) -> dict[str, Any]:

    dietary = state.get("dietary_preference")
    allergy_status = state.get("allergy_status", "unknown")
    allergens = state.get("allergens", [])
    intent = state.get("intent", "unclear")

    # Ask for dietary preference first.
    if dietary is None:
        response = (
            "Do you prefer vegetarian, non-vegetarian, egg-based food, or do you have no preference?"
        )
    # Ask about allergies next.
    elif allergy_status == "unknown":
        response = (
            "Do you have any food allergies? "
            "If not, please say none."
        )
    # Ask for specific allergens if the customer hasn't named them.
    elif allergy_status == "has_allergies" and not allergens:
        response = (
            "Which specific food allergies should I consider?"
        )
    # Preferences are complete, but the customer's intent is unclear.
    elif intent == "unclear":
        response = (
            "What would you like help with? "
            "I can help you explore the menu or find food recommendations."
        )
    else:
        response = "Could you please clarify what you're looking for?"

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

        intent = state.get("intent", "unclear")

        # Preference information has been collected.
        if intent == "preference_only":
            response_text = (
                "Thanks for sharing your preferences! "
                "What would you like to explore from our menu?"
            )

        # Cart functionality is not connected yet.
        elif intent == "cart_action":
            response_text = (
                "I can help with cart operations once that functionality is available. I haven't made any changes to your cart."
            )

        else:
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
                        f"Customer intent: {intent}\n\n"
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
