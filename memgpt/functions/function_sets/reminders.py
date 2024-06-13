import os
from typing import Optional
from memgpt.agent import Agent
import requests

BASE_URL = os.environ['WA_API_URL'] 

DEFAULT_HEADERS = {
    "Accept": "application/json",
    "Content-Type": "application/json",
}


def create_reminder(
    self: Agent,
    description: str,
    recurrence_rule: Optional[str] = None,
    timestamp: Optional[str] = None,
    delay_minutes: Optional[int] = None
) -> str:
    """
    Creates a new reminder in the knowledge base with the given attributes. Useful for keeping track of reminders.

    Examples:
        These should not use recurrence rules:
        "Remind me to take my meds in 30 minutes": runs 30 minutes from now.
        "Remind me to call mom at 19:30": runs at 19:30 today.
        "Remind me to call dad at 19:30 tomorrow": same thing, but tomorrow

        These should use a recurrence rule:
        "Remind me to pray everyday at 21:30": FREQ=DAILY;BYHOUR=21;BYMINUTE=30;BYSECOND=0
        "Every fourth thursday at 19:30": FREQ=MONTHLY;BYDAY=+4TH;BYHOUR=19;BYMINUTE=30;BYSECOND=0
        "Remind me to bathe every weekday at 21": FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR;BYHOUR=21;BYMINUTE=0;BYSECOND=0

    Note:
        - If it is a one-off event, the recurrence rule should use COUNT=1.
        - If the description of the reminder contains a specific time, the recurrence rule should always include the BYHOUR, BYMINUTE, and BYSECOND fields. If there is no minute specified in the description, it should default to 0. BYSECOND should always be 0.

    Args:
        description (str): The description of the reminder. Eg.: "Pick up groceries at 17:35 today"
        recurrence_rule (Optional[str]): The recurrence rule of the reminder. Eg.: "FREQ=DAILY;COUNT=1;BYHOUR=17;BYMINUTE=35;BYSECOND=0"
        timestamp (Optional[str]): A specific timestamp to schedule the reminder. Takes precedence over delay_minutes if both are provided. Format: "YYYY-MM-DD HH:mm:ss"
        delay_minutes (Optional[int]): The number of minutes from now to schedule the reminder. Ignored if timestamp is provided.

    Returns:
        str: A message indicating that the reminder has been added.
    """
    url = f"{BASE_URL}/reminders"
    payload = {
        "agentId": str(self.agent_state.id),
        "description": description,
        "recurrenceRule": recurrence_rule,
        "timestamp": timestamp,
        "delayMinutes": delay_minutes
    }

    try:
        response = requests.post(url, json=payload, headers=DEFAULT_HEADERS)
        response.raise_for_status()
        result = response.json()
        return result["message"]
    except requests.exceptions.RequestException as e:
        print(f"Error creating reminder: {e}")
        return "An error occurred while creating the reminder."


def delete_reminder(self: Agent, reminder_id: int) -> str:
    """
    Deletes an existing reminder by exact description match or by ID for the current agent.

    Args:
        description (Optional[str]): The exact description of the reminder to delete.
        reminder_id (Optional[int]): The ID of the reminder to delete.

    Returns:
        str: A message indicating whether the reminder was deleted or not found.
    """
    url = f"{BASE_URL}/reminders/{reminder_id}"

    try:
        response = requests.delete(url, headers=DEFAULT_HEADERS)
        response.raise_for_status()
        result = response.json()
        return result["message"]
    except requests.exceptions.RequestException as e:
        print(f"Error deleting reminder: {e}")
        return "An error occurred while deleting the reminder."


def list_reminders(self: Agent, page: Optional[int] = 0) -> str:
    """
    Lists existing reminders in the knowledge base for the current agent. Supports pagination.

    Args:
        page (Optional[int]): Allows you to page through results. Defaults to 0 (first page).

    Returns:
        str: A string listing the reminders or indicating that no reminders were found for the current agent.
    """
    # add agent_id to the query
    agent_id = str(self.agent_state.id)
    url = f"{BASE_URL}/reminders?page={page}&agentId={agent_id}"

    try:
        response = requests.get(url, headers=DEFAULT_HEADERS)
        response.raise_for_status()
        result = response.json()

        reminders = result["reminders"]
        pagination = result["pagination"]

        if len(reminders) == 0:
            return "No reminders found."

        results_pref = f"Showing {len(reminders)} of {pagination['total']} reminders (page {pagination['page']+1}/{pagination['totalPages']}):"
        results_formatted = [
            f"ID: {reminder['id']}, Description: {reminder['description']}, Recurrence Rule: {reminder['recurrenceRule']}, Created At: {reminder['createdAt']}, Modified At: {reminder['updatedAt']}"
            for reminder in reminders
        ]
        results_str = f"{results_pref}\n" + "\n".join(results_formatted)
        return results_str
    except requests.exceptions.RequestException as e:
        print(f"Error listing reminders: {e}")
        return "An error occurred while listing the reminders."
