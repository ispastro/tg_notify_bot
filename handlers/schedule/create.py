# handlers/schedule/create.py
"""Schedule creation flow."""
from aiogram import types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from datetime import datetime, timedelta
from loader import dp
from db.session import AsyncSessionLocal
from db.models import Batch, ScheduleType
from sqlalchemy import select
from keyboard.inline import get_batch_keyboard, get_schedule_type_keyboard
from .states import ScheduleStates
from .helpers import ensure_user_exists, format_12hour, save_schedule
from .ui import create_calendar
import logging

logger = logging.getLogger(__name__)


# ----------------------------------------------------------------------
# /schedule COMMAND
# ----------------------------------------------------------------------
@dp.message(Command("schedule"))
async def cmd_schedule(message: types.Message, state: FSMContext):
    """Start schedule creation flow."""
    if not await ensure_user_exists(message.from_user.id, message.from_user.username):
        await message.answer("You don't have permission to use this command.")
        return

    async with AsyncSessionLocal() as session:
        batches = (await session.execute(select(Batch))).scalars().all()

    if not batches:
        await message.answer("No batches found in the database.")
        return

    await message.answer("Select target batches:", reply_markup=get_batch_keyboard(batches))
    await state.set_state(ScheduleStates.choosing_batches)


# ----------------------------------------------------------------------
# BATCH SELECTION
# ----------------------------------------------------------------------
@dp.callback_query(F.data.startswith("batch_"))
async def process_batch(callback: types.CallbackQuery, state: FSMContext):
    """Toggle batch selection."""
    if not await ensure_user_exists(callback.from_user.id):
        await callback.answer("No permission.", show_alert=True)
        return

    batch_id = int(callback.data.split("_")[1])
    data = await state.get_data()
    selected = data.get("batches", [])
    if batch_id in selected:
        selected.remove(batch_id)
    else:
        selected.append(batch_id)
    await state.update_data(batches=selected)

    async with AsyncSessionLocal() as session:
        batches = (await session.execute(select(Batch))).scalars().all()

    await callback.message.edit_reply_markup(reply_markup=get_batch_keyboard(batches, selected))


@dp.callback_query(F.data == "done_batches")
async def done_batches(callback: types.CallbackQuery, state: FSMContext):
    """Confirm batch selection and move to type selection."""
    if not await ensure_user_exists(callback.from_user.id):
        await callback.answer("No permission.", show_alert=True)
        return

    data = await state.get_data()
    selected_batches = data.get("batches", [])

    if not selected_batches:
        await callback.answer("Please select at least one batch!", show_alert=True)
        return

    await callback.answer()

    await callback.message.edit_text(
        f"Selected batches: {len(selected_batches)}\n\nNow choose the schedule type:",
        reply_markup=get_schedule_type_keyboard()
    )

    await state.set_state(ScheduleStates.choosing_type)


# ----------------------------------------------------------------------
# SCHEDULE TYPE SELECTION
# ----------------------------------------------------------------------
@dp.callback_query(F.data.startswith("type_"))
async def process_schedule_type(callback: types.CallbackQuery, state: FSMContext):
    """Handle schedule type selection."""
    if not await ensure_user_exists(callback.from_user.id):
        await callback.answer("No permission.", show_alert=True)
        return

    type_map = {
        "type_weekly": ScheduleType.WEEKLY,
        "type_monthly": ScheduleType.MONTHLY,
        "type_custom": ScheduleType.CUSTOM,
    }

    schedule_type = type_map.get(callback.data)
    if not schedule_type:
        await callback.answer("Invalid type!", show_alert=True)
        return
    
    current_state = await state.get_state()

    # Check if this is from edit flow (handled in edit.py)
    if current_state and "editing" in current_state:
        return

    await state.update_data(schedule_type=schedule_type)
    await callback.answer()

    if schedule_type == ScheduleType.CUSTOM:
        await callback.message.edit_text(
            "⏰ <b>Custom Schedule</b>\n\n"
            "Select the date:",
            reply_markup=create_calendar(),
            parse_mode="HTML"
        )
        await state.set_state(ScheduleStates.choosing_date)
    else:
        await callback.message.edit_text(
            f"Schedule type: <b>{schedule_type.value.title()}</b>\n\n"
            "Now select the start date:",
            reply_markup=create_calendar(),
            parse_mode="HTML"
        )
        await state.set_state(ScheduleStates.choosing_date)


# ----------------------------------------------------------------------
# DATE SELECTION
# ----------------------------------------------------------------------
@dp.callback_query(F.data.startswith("cal_day_"))
async def calendar_day_selected(callback: types.CallbackQuery, state: FSMContext):
    """Handle date selection from calendar."""
    if not await ensure_user_exists(callback.from_user.id):
        await callback.answer("No permission.", show_alert=True)
        return

    parts = callback.data.split("_")
    year, month, day = int(parts[2]), int(parts[3]), int(parts[4])
    selected_date = datetime(year, month, day)

    # Check if date is in the past
    if selected_date.date() < datetime.utcnow().date():
        await callback.answer("Cannot select a past date!", show_alert=True)
        return

    await state.update_data(selected_date=selected_date)
    await callback.answer()

    await callback.message.edit_text(
        f"Date selected: <b>{selected_date.strftime('%b %d, %Y')}</b>\n\n"
        "⏰ Enter the time (12-hour format):\n\n"
        "<b>Examples:</b>\n"
        "• 9:00 AM\n"
        "• 2:30 PM\n"
        "• 6:45 PM\n"
        "• 11:15 AM",
        parse_mode="HTML"
    )
    await state.set_state(ScheduleStates.choosing_time)


# ----------------------------------------------------------------------
# TIME INPUT (12-HOUR FORMAT)
# ----------------------------------------------------------------------
@dp.message(ScheduleStates.choosing_time)
async def process_time_input(message: types.Message, state: FSMContext):
    """Process 12-hour format time input (e.g., '2:30 PM')."""
    if not await ensure_user_exists(message.from_user.id):
        await message.answer("No permission.")
        return

    time_text = message.text.strip()
    data = await state.get_data()
    selected_date = data.get("selected_date")

    if not selected_date:
        await message.answer("Please select a date first using /schedule")
        return

    # Parse 12-hour format time
    try:
        time_obj = datetime.strptime(time_text.upper(), "%I:%M %p")
        hour = time_obj.hour
        minute = time_obj.minute
    except ValueError:
        await message.answer(
            "❌ Invalid time format!\n\n"
            "Please use 12-hour format:\n"
            "<b>Examples:</b>\n"
            "• 9:00 AM\n"
            "• 2:30 PM\n"
            "• 6:45 PM",
            parse_mode="HTML"
        )
        return

    # Combine date + time (Ethiopia is UTC+3)
    # Convert Ethiopia time to UTC for storage
    next_run = selected_date.replace(hour=hour, minute=minute, second=0, microsecond=0)
    # Subtract 3 hours to convert from Ethiopia time to UTC
    next_run_utc = next_run - timedelta(hours=3)

    # Check if the datetime is in the past
    if next_run_utc <= datetime.utcnow():
        await message.answer("❌ Cannot schedule in the past! Pick a future time.")
        return

    await state.update_data(next_run=next_run_utc)

    # Show confirmation in Ethiopia time with proper formatting
    ethiopia_display = format_12hour(next_run_utc)
    await message.answer(
        f"✅ Scheduled for: <b>{ethiopia_display}</b>\n\n"
        "Now enter the message you want to send:\n\n"
        "💡 <i>Tip: Each user will receive a personalized greeting with their name</i>",
        parse_mode="HTML"
    )
    await state.set_state(ScheduleStates.entering_message)


# ----------------------------------------------------------------------
# TIME SELECTION - BUTTON PICKER (LEGACY - FOR WEEKLY/MONTHLY)
# ----------------------------------------------------------------------
@dp.callback_query(F.data.startswith("time_"))
async def process_time_selection(callback: types.CallbackQuery, state: FSMContext):
    """Handle time selection from button picker (legacy)."""
    if not await ensure_user_exists(callback.from_user.id):
        await callback.answer("No permission.", show_alert=True)
        return

    hour = int(callback.data.split("_")[1])
    data = await state.get_data()
    selected_date = data.get("selected_date")

    if not selected_date:
        await callback.answer("Please select a date first!", show_alert=True)
        return

    # Combine date + time
    next_run = selected_date.replace(hour=hour, minute=0, second=0, microsecond=0)

    # Check if the datetime is in the past
    if next_run <= datetime.utcnow():
        await callback.answer("Cannot schedule in the past! Pick a future time.", show_alert=True)
        return

    await state.update_data(next_run=next_run)
    await callback.answer()

    nice_time = format_12hour(next_run)
    await callback.message.edit_text(
        f"Scheduled for: <b>{nice_time}</b>\n\n"
        "Now enter the message you want to send:",
        parse_mode="HTML"
    )
    await state.set_state(ScheduleStates.entering_message)


# ----------------------------------------------------------------------
# MESSAGE INPUT
# ----------------------------------------------------------------------
@dp.message(ScheduleStates.entering_message)
async def process_message(message: types.Message, state: FSMContext):
    """Process message content or media for schedule."""
    if not await ensure_user_exists(message.from_user.id):
        await message.answer("No permission.")
        return

    # Handle different message types
    media_type = None
    media_file_id = None
    caption = None
    text_message = None
    
    if message.photo:
        media_type = "photo"
        media_file_id = message.photo[-1].file_id  # Get highest resolution
        caption = message.caption
    elif message.video:
        media_type = "video"
        media_file_id = message.video.file_id
        caption = message.caption
    elif message.document:
        media_type = "document"
        media_file_id = message.document.file_id
        caption = message.caption
    elif message.text:
        text_message = message.text
    else:
        await message.answer("❌ Unsupported message type. Please send text, photo, video, or document.")
        return
    
    # Store in state
    await state.update_data(
        message_text=text_message,
        media_type=media_type,
        media_file_id=media_file_id,
        caption=caption
    )
    
    data = await state.get_data()

    async with AsyncSessionLocal() as session:
        batch_names = [
            (await session.execute(select(Batch.name).where(Batch.id == bid))).scalar_one()
            for bid in data["batches"]
        ]

    nice_time = format_12hour(data["next_run"])
    
    # Build preview based on content type
    if media_type:
        media_icon = {"photo": "📷", "video": "🎥", "document": "📄"}.get(media_type, "")
        content_preview = f"{media_icon} <b>Media:</b> {media_type.title()}"
        if caption:
            content_preview += f"\n<b>Caption:</b>\n<pre>{caption}</pre>"
    else:
        content_preview = f"<b>Message:</b>\n<pre>{text_message}</pre>"

    preview = (
        f"<b>New Schedule</b>\n\n"
        f"<b>Batches:</b> {', '.join(batch_names)}\n"
        f"<b>Type:</b> {data['schedule_type'].value.title()}\n"
        f"<b>Send Time:</b> {nice_time}\n\n"
        f"{content_preview}\n\n"
        f"💡 <i>Note: 'ሰላም [Name]' will be automatically added for each user</i>\n\n"
        f"Send this schedule?"
    )

    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="✅ Confirm & Send", callback_data="confirm_schedule")],
        [types.InlineKeyboardButton(text="❌ Cancel", callback_data="cancel_schedule")]
    ])

    await message.answer(preview, reply_markup=kb, parse_mode="HTML")
    await state.set_state(ScheduleStates.confirming)


# ----------------------------------------------------------------------
# CONFIRM & CANCEL
# ----------------------------------------------------------------------
@dp.callback_query(F.data == "confirm_schedule")
async def confirm_schedule(callback: types.CallbackQuery, state: FSMContext):
    """Confirm and save the schedule."""
    if not await ensure_user_exists(callback.from_user.id):
        await callback.answer("No permission.", show_alert=True)
        return

    data = await state.get_data()
    
    # Debug logging
    logger.info(f"Confirming schedule. State data keys: {data.keys()}")
    logger.info(f"message_text present: {'message_text' in data}")
    logger.info(f"message_text value: {data.get('message_text')}")
    
    saved = await save_schedule(data, callback.from_user.id)

    if not saved:
        await callback.message.edit_text("❌ Failed to create schedule. Please try again.")
        await state.clear()
        return

    await callback.message.edit_text(
        f"Schedule <b>#{saved.id}</b> Created Successfully!\n\n"
        f"Will send: <b>{format_12hour(saved.next_run)}</b>\n"
        f"Type: <b>{saved.type.value.title()}</b>",
        parse_mode="HTML"
    )
    await state.clear()


@dp.callback_query(F.data == "cancel_schedule")
async def cancel_schedule(callback: types.CallbackQuery, state: FSMContext):
    """Cancel schedule creation."""
    await callback.message.edit_text("Schedule cancelled.")
    await state.clear()
