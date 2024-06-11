import os
import shelve
import datetime
import math
from typing import Optional
from memgpt.agent import Agent
from dateutil.rrule import rrulestr
import requests
import pytz
from memgpt.scheduler import get_scheduler

BASE_URL = "http://localhost:8083/api"
MEMGPT_SERVER_PASS = os.environ["MEMGPT_SERVER_PASS"]

DEFAULT_HEADERS = {
    "Accept": "application/json",
    "Content-Type": "application/json",
    "Authorization": f"Bearer {MEMGPT_SERVER_PASS}",
}

SAO_PAULO_TIMEZONE = pytz.timezone('America/Sao_Paulo')


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
    with shelve.open("reminders.shelve") as db:
        # Check for existing reminders with the same description for the current agent
        agent_reminders = [reminder for reminder in db.values() if reminder["agent_id"] == self.agent_state.id]
        for reminder in agent_reminders:
            if reminder["description"] == description:
                return f"Reminder with description '{description}' already exists."

        # Determine the new reminder ID
        if agent_reminders:
            last_id = max(reminder["id"] for reminder in agent_reminders)
        else:
            last_id = 0
        new_id = last_id + 1

        current_time = datetime.datetime.now(SAO_PAULO_TIMEZONE)
        reminder = {
            "id": new_id,
            "agent_id": self.agent_state.id,
            "description": description,
            "recurrence_rule": recurrence_rule,
            "created_at": current_time.isoformat(),
            "modified_at": current_time.isoformat(),
        }
        db[str(new_id)] = reminder

    # Define the send_message function inside create_reminder
    def send_message(agent_id: str, message: str):
        url = f"{BASE_URL}/agents/{agent_id}/messages"
        payload = { "message": message }
        print(f"Sending message to {url} with payload: {payload}")
        response = requests.post(url, json=payload, headers=DEFAULT_HEADERS)
        print(f"Message sent with response status: {response.status_code}")
        return response

    # Define the scheduling function inside create_reminder
    def schedule_reminder(reminder_id: int, description: str, recurrence_rule: Optional[str], timestamp: Optional[str], delay_minutes: Optional[int]):
        print(f"Scheduling reminder with ID {reminder_id} and description '{description}'")
        
        if recurrence_rule:
            rule = rrulestr(recurrence_rule, dtstart=current_time)
            next_occurrence = rule.after(current_time)
        elif timestamp:
            next_occurrence = datetime.datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S").replace(tzinfo=SAO_PAULO_TIMEZONE)
        elif delay_minutes:
            next_occurrence = current_time + datetime.timedelta(minutes=delay_minutes)
        else:
            raise ValueError("Either recurrence_rule, timestamp or delay_minutes must be provided")
        
        print(f"Next occurrence calculated: {next_occurrence}")

        def execute_reminder():
            current_time_str = datetime.datetime.now(SAO_PAULO_TIMEZONE).strftime('%Y-%m-%d %H:%M:%S')
            message = f"> SYS: It is {current_time_str}, remind the user about his scheduled reminder: '{description}'"
            print(f"Executing reminder ID {reminder_id} at {current_time_str}")
            response = send_message(self.agent_state.id, message)
            print(f"Message sent with response status: {response.status_code}")
            
            # Schedule the next occurrence if there is a recurrence rule
            if recurrence_rule:
                next_occurrence = rule.after(datetime.datetime.now(SAO_PAULO_TIMEZONE))
                if next_occurrence:
                    print(f"Scheduling next occurrence for reminder ID {reminder_id} at {next_occurrence}")
                    scheduler = get_scheduler()
                    scheduler.add_job(execute_reminder, 'date', run_date=next_occurrence, id=f"reminder_{reminder_id}")
                else:
                    # If there is no next occurrence, delete the reminder from the database
                    with shelve.open("reminders.shelve") as db:
                        if str(reminder_id) in db:
                            del db[str(reminder_id)]
                            print(f"Reminder ID {reminder_id} deleted from the database as there are no more occurrences.")
        
        scheduler = get_scheduler()
        scheduler.add_job(execute_reminder, 'date', run_date=next_occurrence, id=f"reminder_{reminder_id}")
        return next_occurrence

    # Schedule the reminder and get the next occurrence
    next_occurrence = schedule_reminder(new_id, description, recurrence_rule, timestamp, delay_minutes)

    return f"Reminder '{description}' has been added. Next occurrence: {next_occurrence}"


def delete_reminder(self: Agent, description: Optional[str] = None, reminder_id: Optional[int] = None) -> str:
    """
    Deletes an existing reminder by exact description match or by ID for the current agent.

    Args:
        description (Optional[str]): The exact description of the reminder to delete.
        reminder_id (Optional[int]): The ID of the reminder to delete.

    Returns:
        str: A message indicating whether the reminder was deleted or not found.
    """
    if description is None and reminder_id is None:
        return "Please provide either a description or an ID to delete a reminder."

    with shelve.open("reminders.shelve") as db:
        agent_reminders = [reminder for reminder in db.values() if reminder["agent_id"] == self.agent_state.id]
        reminder_to_delete = None

        if description is not None:
            for reminder in agent_reminders:
                if reminder["description"] == description:
                    reminder_to_delete = reminder
                    break

        if reminder_id is not None:
            for reminder in agent_reminders:
                if reminder["id"] == reminder_id:
                    reminder_to_delete = reminder
                    break

        if reminder_to_delete is None:
            return "Reminder not found."

        del db[str(reminder_to_delete["id"])]
        
        # Cancel the scheduled execution of the reminder
        scheduler = get_scheduler()
        scheduler.remove_job(f"reminder_{reminder_to_delete['id']}")
        
        return f"Reminder '{reminder_to_delete['description']}' has been deleted."


def list_reminders(self: Agent, page: Optional[int] = 0) -> str:
    """
    Lists existing reminders in the knowledge base for the current agent. Supports pagination.

    Args:
        page (Optional[int]): Allows you to page through results. Defaults to 0 (first page).

    Returns:
        str: A string listing the reminders or indicating that no reminders were found for the current agent.
    """
    if page is None or (isinstance(page, str) and page.lower().strip() == "none"):
        page = 0
    try:
        page = int(page)
    except ValueError:
        raise ValueError(f"'page' argument must be an integer")

    count = 10  # Number of reminders per page
    with shelve.open("reminders.shelve") as db:
        agent_reminders = [reminder for reminder in db.values() if reminder["agent_id"] == self.agent_state.id]
        total = len(agent_reminders)
        num_pages = math.ceil(total / count)  # Total number of pages

        if total == 0:
            return "No reminders found."

        start = page * count
        end = start + count
        paginated_reminders = agent_reminders[start:end]

        results_pref = f"Showing {len(paginated_reminders)} of {total} reminders (page {page+1}/{num_pages}):"
        results_formatted = [
            f"ID: {reminder['id']}, Description: {reminder['description']}, Recurrence Rule: {reminder['recurrence_rule']}, Created At: {reminder['created_at']}, Modified At: {reminder['modified_at']}"
            for reminder in paginated_reminders
        ]
        results_str = f"{results_pref}\n" + "\n".join(results_formatted)
        return results_str
