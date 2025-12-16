# handlers/schedule.py — PRODUCTION VERSION with Admin Management
from aiogram import types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from loader import dp
from db.session import AsyncSessionLocal
from db.models import User, Batch, Schedule, ScheduleType, schedule_batch_association
from sqlalchemy import select, update, delete
from keyboard.inline import (
    get_batch_keyboard, 
    get_schedule_type_keyboard,
    get_schedule_list_keyboard,
    get_schedule_actions_keyboard,
    get_edit_options_keyboard,
    get_confirm_delete_keyboard,
    get_edit_batch_keyboard,
    get_cancel_keyboard,
)
from config import SUPER_ADMIN_ID
from datetime import datetime
import calendar
import asyncio
import logging
from sqlalchemy.orm import selectinload

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ----------------------------------------------------------------------
# FSM STATES - Schedule Creation
# ----------------------------------------------------------------------
class ScheduleStates(StatesGroup):
    choosing_batches = State()
    choosing_type = State()
    choosing_date = State()
    choosing_time = State()
    entering_message = State()
    confirming = State()


# ----------------------------------------------------------------------
# FSM STATES - Schedule Editing
# ----------------------------------------------------------------------
class EditScheduleStates(StatesGroup):
    editing_message = State()
    editing_date = State()
    editing_time = State()
    editing_batches = State()
    editing_type = State()
    editing_cron = State()


# ----------------------------------------------------------------------
# AUTO-CREATE USER + ADMIN CHECK
# ----------------------------------------------------------------------
async def ensure_user_exists(user_id: int, username: str | None = None) -> bool:
    async with AsyncSessionLocal() as session:
        try:
            result = await session.execute(select(User).where(User.user_id == user_id))
            user = result.scalar_one_or_none()

            if not user:
                is_super = (user_id == SUPER_ADMIN_ID)
                new_user = User(
                    user_id=user_id,
                    username=username or "Unknown",
                    full_name="Admin",
                    is_admin=is_super,
                    join_date=datetime.utcnow()
                )
                session.add(new_user)
                await session.commit()
                logger.info(f"NEW USER CREATED: {user_id} | SuperAdmin: {is_super}")
                return True  # Admins always allowed

            return user.is_admin or (user_id == SUPER_ADMIN_ID)
        except Exception as e:
            logger.error(f"USER CHECK FAILED: {e}")
            return False


# ----------------------------------------------------------------------
# 12-HOUR FORMAT HELPER
# ----------------------------------------------------------------------
def format_12hour(dt: datetime) -> str:
    period = "AM" if dt.hour < 12 else "PM"
    hour = dt.hour % 12
    hour = 12 if hour == 0 else hour
    return f"{dt.strftime('%b %d, %Y')} at {hour}:00 {period} UTC"


# ----------------------------------------------------------------------
# CALENDAR (unchanged, beautiful)
# ----------------------------------------------------------------------
def create_calendar(year: int | None = None, month: int | None = None):
    now = datetime.utcnow()
    year = year or now.year
    month = month or now.month

    inline = []
    month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    prev = types.InlineKeyboardButton(text="Previous", callback_data=f"cal_prev_{year}_{month}")
    nxt = types.InlineKeyboardButton(text="Next", callback_data=f"cal_next_{year}_{month}")
    title = types.InlineKeyboardButton(text=f"{month_names[month - 1]} {year}", callback_data="ignore")
    inline.append([prev, title, nxt])

    days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    inline.append([types.InlineKeyboardButton(text=d, callback_data="ignore") for d in days])

    cal = calendar.monthcalendar(year, month)
    for week in cal:
        row = []
        for day in week:
            if day == 0:
                row.append(types.InlineKeyboardButton(text=" ", callback_data="ignore"))
            else:
                txt = f"*{day}" if datetime(year, month, day).date() == now.date() else str(day)
                row.append(types.InlineKeyboardButton(text=txt, callback_data=f"cal_day_{year}_{month}_{day}"))
        inline.append(row)

    return types.InlineKeyboardMarkup(inline_keyboard=inline)


# ----------------------------------------------------------------------
# 12-HOUR TIME PICKER — BEAUTIFUL & CLEAN
# ----------------------------------------------------------------------
def create_time_picker():
    inline = []
    # AM Hours
    row = []
    for h in range(12):
        hour_12 = 12 if h == 0 else h
        text = f"{hour_12}:00 AM"
        callback = f"time_{h}"
        row.append(types.InlineKeyboardButton(text=text, callback_data=callback))
        if len(row) == 3:
            inline.append(row)
            row = []
    if row:
        inline.append(row)

    # PM Hours
    row = []
    for h in range(12, 24):
        hour_12 = h - 12
        hour_12 = 12 if hour_12 == 0 else hour_12
        text = f"{hour_12}:00 PM"
        callback = f"time_{h}"
        row.append(types.InlineKeyboardButton(text=text, callback_data=callback))
        if len(row) == 3:
            inline.append(row)
            row = []
    if row:
        inline.append(row)

    return types.InlineKeyboardMarkup(inline_keyboard=inline)


# ----------------------------------------------------------------------
# /schedule COMMAND
# ----------------------------------------------------------------------
@dp.message(Command("schedule"))
async def cmd_schedule(message: types.Message, state: FSMContext):
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
# BATCH SELECTION (unchanged)
# ----------------------------------------------------------------------
@dp.callback_query(F.data.startswith("batch_"))
async def process_batch(callback: types.CallbackQuery, state: FSMContext):
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
#the done button
@dp.callback_query(F.data == "done_batches")
async def done_batches(callback: types.CallbackQuery, state: FSMContext):
    if not await ensure_user_exists(callback.from_user.id):
        await callback.answer("No permission.", show_alert=True)
        return

    data = await state.get_data()
    selected_batches = data.get("batches", [])

    if not selected_batches:
        await callback.answer("Please select at least one batch!", show_alert=True)
        return

    # Success: at least one batch selected
    await callback.answer()  # Remove loading spinner

    # Show how many batches selected + proceed
    await callback.message.edit_text(
        f"Selected batches: {len(selected_batches)}\n\nNow choose the schedule type:",
        reply_markup=get_schedule_type_keyboard()
    )

    await state.set_state(ScheduleStates.choosing_type)


# ----------------------------------------------------------------------
# SCHEDULE TYPE SELECTION (CREATION & EDITING)
# ----------------------------------------------------------------------
@dp.callback_query(F.data.startswith("type_"))
async def process_schedule_type(callback: types.CallbackQuery, state: FSMContext):
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

    # CHECK IF EDITING
    if current_state == EditScheduleStates.editing_type:
        await state.update_data(editing_new_type=schedule_type)
        if schedule_type == ScheduleType.CUSTOM:
            await callback.message.edit_text(
                "📅 <b>Edit Type: Custom</b>\n\n"
                "Enter a new cron expression (e.g., <code>0 9 * * 1</code>):\n"
                "Format: <code>minute hour day month weekday</code>",
                reply_markup=get_cancel_keyboard(0), # 0 or valid ID if I have it in data?
                parse_mode="HTML"
            )
            await state.set_state(EditScheduleStates.editing_cron)
        else:
            await callback.message.edit_text(
                f"📅 <b>Edit Type: {schedule_type.value.title()}</b>\n\n"
                "Select the new start date:",
                reply_markup=create_calendar(),
                parse_mode="HTML"
            )
            # We reuse editing_date for picking date -> then editing_time
            await state.set_state(EditScheduleStates.editing_date)
        
        await callback.answer()
        return

    # EXISTING CREATION FLOW
    await state.update_data(schedule_type=schedule_type)
    await callback.answer()

    if schedule_type == ScheduleType.CUSTOM:
        # Custom: Ask for cron expression
        await callback.message.edit_text(
            "Enter a cron expression (e.g., <code>0 9 * * 1</code> for every Monday at 9 AM UTC):\n\n"
            "Format: <code>minute hour day month weekday</code>",
            parse_mode="HTML"
        )
        await state.set_state(ScheduleStates.choosing_date)  # Reuse for cron input
    else:
        # Weekly/Monthly: Show calendar to pick a date
        await callback.message.edit_text(
            f"Schedule type: <b>{schedule_type.value.title()}</b>\n\n"
            "Now select the start date:",
            reply_markup=create_calendar(),
            parse_mode="HTML"
        )
        await state.set_state(ScheduleStates.choosing_date)


# ----------------------------------------------------------------------
# CALENDAR NAVIGATION
# ----------------------------------------------------------------------
@dp.callback_query(F.data.startswith("cal_prev_"))
async def calendar_prev(callback: types.CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    year, month = int(parts[2]), int(parts[3])
    # Go to previous month
    if month == 1:
        year -= 1
        month = 12
    else:
        month -= 1
    await callback.message.edit_reply_markup(reply_markup=create_calendar(year, month))
    await callback.answer()


@dp.callback_query(F.data.startswith("cal_next_"))
async def calendar_next(callback: types.CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    year, month = int(parts[2]), int(parts[3])
    # Go to next month
    if month == 12:
        year += 1
        month = 1
    else:
        month += 1
    await callback.message.edit_reply_markup(reply_markup=create_calendar(year, month))
    await callback.answer()


@dp.callback_query(F.data.startswith("cal_day_"))
async def calendar_day_selected(callback: types.CallbackQuery, state: FSMContext):
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
        "Now select the time:",
        reply_markup=create_time_picker(),
        parse_mode="HTML"
    )
    await state.set_state(ScheduleStates.choosing_time)


@dp.callback_query(F.data == "ignore")
async def ignore_callback(callback: types.CallbackQuery):
    await callback.answer()


# ----------------------------------------------------------------------
# TIME SELECTION
# ----------------------------------------------------------------------
@dp.callback_query(F.data.startswith("time_"))
async def process_time_selection(callback: types.CallbackQuery, state: FSMContext):
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
# CRON EXPRESSION INPUT (for Custom type)
# ----------------------------------------------------------------------
@dp.message(ScheduleStates.choosing_date)
async def process_cron_or_date(message: types.Message, state: FSMContext):
    """Handle cron expression input for CUSTOM schedule type."""
    if not await ensure_user_exists(message.from_user.id):
        await message.answer("No permission.")
        return

    data = await state.get_data()
    schedule_type = data.get("schedule_type")

    if schedule_type == ScheduleType.CUSTOM:
        # Validate cron expression
        import croniter
        try:
            cron = croniter.croniter(message.text.strip(), datetime.utcnow())
            next_run = cron.get_next(datetime)
        except Exception as e:
            await message.answer(
                f"Invalid cron expression: <code>{message.text}</code>\n\n"
                f"Error: {e}\n\n"
                "Please try again with a valid cron format.",
                parse_mode="HTML"
            )
            return

        await state.update_data(
            cron_expr=message.text.strip(),
            next_run=next_run
        )

        nice_time = format_12hour(next_run)
        await message.answer(
            f"Cron: <code>{message.text.strip()}</code>\n"
            f"Next run: <b>{nice_time}</b>\n\n"
            "Now enter the message you want to send:",
            parse_mode="HTML"
        )
        await state.set_state(ScheduleStates.entering_message)


# ----------------------------------------------------------------------
@dp.message(ScheduleStates.entering_message)
async def process_message(message: types.Message, state: FSMContext):
    if not await ensure_user_exists(message.from_user.id):
        await message.answer("No permission.")
        return

    await state.update_data(message_text=message.text)
    data = await state.get_data()

    async with AsyncSessionLocal() as session:
        batch_names = [
            (await session.execute(select(Batch.name).where(Batch.id == bid))).scalar_one()
            for bid in data["batches"]
        ]

    nice_time = format_12hour(data["next_run"])

    preview = (
        f"<b>New Schedule</b>\n\n"
        f"<b>Batches:</b> {', '.join(batch_names)}\n"
        f"<b>Type:</b> {data['schedule_type'].value.title()}\n"
        f"<b>Send Time:</b> <code>{nice_time}</code>\n\n"
        f"<b>Message:</b>\n<pre>{message.text}</pre>\n\n"
        f"Send this schedule?"
    )

    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="Confirm & Send", callback_data="confirm_schedule")],
        [types.InlineKeyboardButton(text="Cancel", callback_data="cancel_schedule")]
    ])

    await message.answer(preview, reply_markup=kb, parse_mode="HTML")
    await state.set_state(ScheduleStates.confirming)


# ----------------------------------------------------------------------
# SAVE SCHEDULE
# ----------------------------------------------------------------------
async def _save_schedule(data: dict, admin_id: int) -> Schedule | None:
    async with AsyncSessionLocal() as session:
        try:
            sched = Schedule(
                message=data["message_text"],
                type=data["schedule_type"],
                next_run=data["next_run"],
                admin_id=admin_id,
                is_active=True,
            )
            session.add(sched)
            await session.flush()

            for bid in data["batches"]:
                await session.execute(
                    schedule_batch_association.insert().values(schedule_id=sched.id, batch_id=bid)
                )

            await session.commit()
            return sched
        except Exception as e:
            await session.rollback()
            logger.error(f"Schedule save failed: {e}")
            return None


# ----------------------------------------------------------------------
# CONFIRM & CANCEL
# ----------------------------------------------------------------------
@dp.callback_query(F.data == "confirm_schedule")
async def confirm_schedule(callback: types.CallbackQuery, state: FSMContext):
    if not await ensure_user_exists(callback.from_user.id):
        await callback.answer("No permission.", show_alert=True)
        return

    data = await state.get_data()
    saved = await _save_schedule(data, callback.from_user.id)

    if not saved:
        await callback.message.edit_text("Failed to create schedule. Try again.")
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
    await callback.message.edit_text("Schedule cancelled.")
    await state.clear()


# ----------------------------------------------------------------------
# ADMIN: LIST SCHEDULES (12-HOUR FORMAT)
# ----------------------------------------------------------------------
@dp.message(Command("list_schedules"))
async def cmd_list_schedules(message: types.Message):
    if not await ensure_user_exists(message.from_user.id):
        await message.answer("No permission.")
        return

    async with AsyncSessionLocal() as session:
        schedules = (await session.execute(
            select(Schedule).options(selectinload(Schedule.batches)).order_by(Schedule.id)
        )).scalars().all()

    if not schedules:
        await message.answer("No active schedules.")
        return

    lines = []
    for s in schedules:
        status = "Active" if s.is_active else "Paused"
        batches = ", ".join(b.name for b in s.batches) if s.batches else "None"
        lines.append(
            f"<b>#{s.id}</b> | {status}\n"
            f"Batches: <code>{batches}</code>\n"
            f"Next: <code>{format_12hour(s.next_run)}</code>\n"
            f"Type: <code>{s.type.value}</code>\n"
            f"Preview: <i>{s.message[:60]}{'...' if len(s.message)>60 else ''}</i>\n"
        )

    await message.answer(
        f"<b>Scheduled Broadcasts ({len(schedules)})</b>\n\n" + "\n\n".join(lines),
        parse_mode="HTML"
    )


# ==============================================================================
# ADMIN SCHEDULE MANAGEMENT - Interactive UI
# ==============================================================================

# ----------------------------------------------------------------------
# /manage_schedules - Main Entry Point
# ----------------------------------------------------------------------
@dp.message(Command("manage_schedules"))
async def cmd_manage_schedules(message: types.Message, state: FSMContext):
    """Display interactive schedule management panel."""
    if not await ensure_user_exists(message.from_user.id, message.from_user.username):
        await message.answer("❌ You don't have permission to manage schedules.")
        return

    await state.clear()  # Clear any previous state
    
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Schedule).options(selectinload(Schedule.batches)).order_by(Schedule.id.desc())
        )
        schedules = result.scalars().all()

    if not schedules:
        await message.answer(
            "📭 <b>No schedules found.</b>\n\n"
            "Use /schedule to create your first scheduled broadcast.",
            parse_mode="HTML"
        )
        return

    await message.answer(
        f"📋 <b>Schedule Management</b>\n\n"
        f"Total: <code>{len(schedules)}</code> schedule(s)\n"
        f"Active: <code>{sum(1 for s in schedules if s.is_active)}</code> | "
        f"Paused: <code>{sum(1 for s in schedules if not s.is_active)}</code>\n\n"
        f"Select a schedule to manage:",
        reply_markup=get_schedule_list_keyboard(schedules, page=0),
        parse_mode="HTML"
    )


# ----------------------------------------------------------------------
# Pagination Handler
# ----------------------------------------------------------------------
@dp.callback_query(F.data.startswith("sched_page_"))
async def handle_schedule_pagination(callback: types.CallbackQuery, state: FSMContext):
    """Handle pagination in schedule list."""
    if not await ensure_user_exists(callback.from_user.id):
        await callback.answer("No permission.", show_alert=True)
        return

    page = int(callback.data.split("_")[2])
    
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Schedule).options(selectinload(Schedule.batches)).order_by(Schedule.id.desc())
        )
        schedules = result.scalars().all()

    await callback.message.edit_reply_markup(
        reply_markup=get_schedule_list_keyboard(schedules, page=page)
    )
    await callback.answer()


# ----------------------------------------------------------------------
# View Schedule Details
# ----------------------------------------------------------------------
@dp.callback_query(F.data.startswith("sched_view_"))
async def handle_view_schedule(callback: types.CallbackQuery, state: FSMContext):
    """Display detailed view of a single schedule."""
    if not await ensure_user_exists(callback.from_user.id):
        await callback.answer("No permission.", show_alert=True)
        return

    schedule_id = int(callback.data.split("_")[2])
    
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Schedule).options(selectinload(Schedule.batches)).where(Schedule.id == schedule_id)
        )
        sched = result.scalar_one_or_none()

    if not sched:
        await callback.answer("Schedule not found!", show_alert=True)
        return

    status = "🟢 Active" if sched.is_active else "⏸️ Paused"
    batches = ", ".join(b.name for b in sched.batches) if sched.batches else "None"
    next_run_str = format_12hour(sched.next_run) if sched.next_run else "Not scheduled"
    cron_info = f"\n<b>Cron:</b> <code>{sched.cron_expr}</code>" if sched.cron_expr else ""
    
    # Truncate message preview
    msg_preview = sched.message[:200] + "..." if len(sched.message) > 200 else sched.message

    text = (
        f"📅 <b>Schedule #{sched.id}</b>\n\n"
        f"<b>Status:</b> {status}\n"
        f"<b>Type:</b> {sched.type.value.title()}\n"
        f"<b>Batches:</b> {batches}\n"
        f"<b>Next Run:</b> <code>{next_run_str}</code>{cron_info}\n"
        f"<b>Created:</b> {sched.created_at.strftime('%Y-%m-%d %H:%M') if sched.created_at else 'Unknown'}\n\n"
        f"<b>Message Preview:</b>\n<blockquote>{msg_preview}</blockquote>"
    )

    await callback.message.edit_text(
        text,
        reply_markup=get_schedule_actions_keyboard(sched.id, sched.is_active),
        parse_mode="HTML"
    )
    await callback.answer()


# ----------------------------------------------------------------------
# Back to Schedule List
# ----------------------------------------------------------------------
@dp.callback_query(F.data == "sched_back_list")
async def handle_back_to_list(callback: types.CallbackQuery, state: FSMContext):
    """Go back to schedule list."""
    if not await ensure_user_exists(callback.from_user.id):
        await callback.answer("No permission.", show_alert=True)
        return

    await state.clear()
    
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Schedule).options(selectinload(Schedule.batches)).order_by(Schedule.id.desc())
        )
        schedules = result.scalars().all()

    if not schedules:
        await callback.message.edit_text("📭 No schedules found.")
        return

    await callback.message.edit_text(
        f"📋 <b>Schedule Management</b>\n\n"
        f"Total: <code>{len(schedules)}</code> schedule(s)\n"
        f"Active: <code>{sum(1 for s in schedules if s.is_active)}</code> | "
        f"Paused: <code>{sum(1 for s in schedules if not s.is_active)}</code>\n\n"
        f"Select a schedule to manage:",
        reply_markup=get_schedule_list_keyboard(schedules, page=0),
        parse_mode="HTML"
    )
    await callback.answer()


# ----------------------------------------------------------------------
# Create New Schedule (from management panel)
# ----------------------------------------------------------------------
@dp.callback_query(F.data == "sched_create_new")
async def handle_create_new_schedule(callback: types.CallbackQuery, state: FSMContext):
    """Start new schedule creation flow."""
    if not await ensure_user_exists(callback.from_user.id):
        await callback.answer("No permission.", show_alert=True)
        return

    async with AsyncSessionLocal() as session:
        batches = (await session.execute(select(Batch))).scalars().all()

    if not batches:
        await callback.answer("No batches found!", show_alert=True)
        return

    await callback.message.edit_text(
        "➕ <b>Create New Schedule</b>\n\nSelect target batches:",
        reply_markup=get_batch_keyboard(batches),
        parse_mode="HTML"
    )
    await state.set_state(ScheduleStates.choosing_batches)
    await callback.answer()


# ----------------------------------------------------------------------
# Toggle Pause/Resume
# ----------------------------------------------------------------------
@dp.callback_query(F.data.startswith("sched_toggle_"))
async def handle_toggle_schedule(callback: types.CallbackQuery, state: FSMContext):
    """Toggle schedule active/paused status."""
    if not await ensure_user_exists(callback.from_user.id):
        await callback.answer("No permission.", show_alert=True)
        return

    schedule_id = int(callback.data.split("_")[2])
    
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Schedule).options(selectinload(Schedule.batches)).where(Schedule.id == schedule_id)
        )
        sched = result.scalar_one_or_none()
        
        if not sched:
            await callback.answer("Schedule not found!", show_alert=True)
            return
        
        new_status = not sched.is_active
        await session.execute(
            update(Schedule).where(Schedule.id == schedule_id).values(is_active=new_status)
        )
        await session.commit()
        
        # Refresh schedule object
        result = await session.execute(
            select(Schedule).options(selectinload(Schedule.batches)).where(Schedule.id == schedule_id)
        )
        sched = result.scalar_one()

    action = "resumed ▶️" if new_status else "paused ⏸️"
    await callback.answer(f"Schedule #{schedule_id} {action}", show_alert=True)
    
    # Refresh the view
    status = "🟢 Active" if sched.is_active else "⏸️ Paused"
    batches = ", ".join(b.name for b in sched.batches) if sched.batches else "None"
    next_run_str = format_12hour(sched.next_run) if sched.next_run else "Not scheduled"
    cron_info = f"\n<b>Cron:</b> <code>{sched.cron_expr}</code>" if sched.cron_expr else ""
    msg_preview = sched.message[:200] + "..." if len(sched.message) > 200 else sched.message

    text = (
        f"📅 <b>Schedule #{sched.id}</b>\n\n"
        f"<b>Status:</b> {status}\n"
        f"<b>Type:</b> {sched.type.value.title()}\n"
        f"<b>Batches:</b> {batches}\n"
        f"<b>Next Run:</b> <code>{next_run_str}</code>{cron_info}\n"
        f"<b>Created:</b> {sched.created_at.strftime('%Y-%m-%d %H:%M') if sched.created_at else 'Unknown'}\n\n"
        f"<b>Message Preview:</b>\n<blockquote>{msg_preview}</blockquote>"
    )

    await callback.message.edit_text(
        text,
        reply_markup=get_schedule_actions_keyboard(sched.id, sched.is_active),
        parse_mode="HTML"
    )


# ----------------------------------------------------------------------
# Show Edit Menu
# ----------------------------------------------------------------------
@dp.callback_query(F.data.startswith("sched_edit_"))
async def handle_show_edit_menu(callback: types.CallbackQuery, state: FSMContext):
    """Show edit options for a schedule."""
    if not await ensure_user_exists(callback.from_user.id):
        await callback.answer("No permission.", show_alert=True)
        return

    schedule_id = int(callback.data.split("_")[2])
    
    async with AsyncSessionLocal() as session:
        sched = await session.get(Schedule, schedule_id)
        if not sched:
            await callback.answer("Schedule not found!", show_alert=True)
            return

    await callback.message.edit_text(
        f"✏️ <b>Edit Schedule #{schedule_id}</b>\n\n"
        f"What would you like to edit?",
        reply_markup=get_edit_options_keyboard(schedule_id),
        parse_mode="HTML"
    )
    await callback.answer()


# ----------------------------------------------------------------------
# Edit Message Flow
# ----------------------------------------------------------------------
@dp.callback_query(F.data.startswith("edit_msg_"))
async def handle_edit_message_start(callback: types.CallbackQuery, state: FSMContext):
    """Start editing message content."""
    if not await ensure_user_exists(callback.from_user.id):
        await callback.answer("No permission.", show_alert=True)
        return

    schedule_id = int(callback.data.split("_")[2])
    
    async with AsyncSessionLocal() as session:
        sched = await session.get(Schedule, schedule_id)
        if not sched:
            await callback.answer("Schedule not found!", show_alert=True)
            return

    await state.update_data(editing_schedule_id=schedule_id)
    await state.set_state(EditScheduleStates.editing_message)

    await callback.message.edit_text(
        f"📝 <b>Edit Message for Schedule #{schedule_id}</b>\n\n"
        f"<b>Current message:</b>\n<blockquote>{sched.message[:500]}</blockquote>\n\n"
        f"Send the new message:",
        reply_markup=get_cancel_keyboard(schedule_id),
        parse_mode="HTML"
    )
    await callback.answer()


@dp.message(EditScheduleStates.editing_message)
async def process_edit_message(message: types.Message, state: FSMContext):
    """Process new message content."""
    if not await ensure_user_exists(message.from_user.id):
        await message.answer("No permission.")
        return

    data = await state.get_data()
    schedule_id = data.get("editing_schedule_id")
    
    if not schedule_id:
        await message.answer("Error: No schedule selected.")
        await state.clear()
        return

    async with AsyncSessionLocal() as session:
        await session.execute(
            update(Schedule).where(Schedule.id == schedule_id).values(message=message.text)
        )
        await session.commit()
        
        result = await session.execute(
            select(Schedule).options(selectinload(Schedule.batches)).where(Schedule.id == schedule_id)
        )
        sched = result.scalar_one_or_none()

    await state.clear()
    
    if not sched:
        await message.answer("Schedule not found after update.")
        return

    logger.info(f"Schedule #{schedule_id} message updated by admin {message.from_user.id}")

    status = "🟢 Active" if sched.is_active else "⏸️ Paused"
    batches = ", ".join(b.name for b in sched.batches) if sched.batches else "None"
    next_run_str = format_12hour(sched.next_run) if sched.next_run else "Not scheduled"

    await message.answer(
        f"✅ <b>Message Updated!</b>\n\n"
        f"📅 <b>Schedule #{sched.id}</b>\n"
        f"<b>Status:</b> {status}\n"
        f"<b>Batches:</b> {batches}\n"
        f"<b>Next Run:</b> <code>{next_run_str}</code>\n\n"
        f"<b>New Message:</b>\n<blockquote>{sched.message[:200]}{'...' if len(sched.message) > 200 else ''}</blockquote>",
        reply_markup=get_schedule_actions_keyboard(sched.id, sched.is_active),
        parse_mode="HTML"
    )


# ----------------------------------------------------------------------
# Edit Time Flow
# ----------------------------------------------------------------------
@dp.callback_query(F.data.startswith("edit_time_"))
async def handle_edit_time_start(callback: types.CallbackQuery, state: FSMContext):
    """Start editing schedule time."""
    if not await ensure_user_exists(callback.from_user.id):
        await callback.answer("No permission.", show_alert=True)
        return

    schedule_id = int(callback.data.split("_")[2])
    
    async with AsyncSessionLocal() as session:
        sched = await session.get(Schedule, schedule_id)
        if not sched:
            await callback.answer("Schedule not found!", show_alert=True)
            return

    await state.update_data(editing_schedule_id=schedule_id, editing_schedule_type=sched.type)
    await state.set_state(EditScheduleStates.editing_date)

    current_time = format_12hour(sched.next_run) if sched.next_run else "Not set"
    
    await callback.message.edit_text(
        f"🕐 <b>Edit Time for Schedule #{schedule_id}</b>\n\n"
        f"<b>Current:</b> <code>{current_time}</code>\n\n"
        f"Select new date:",
        reply_markup=create_calendar(),
        parse_mode="HTML"
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("edit_cal_day_"), EditScheduleStates.editing_date)
async def handle_edit_calendar_day(callback: types.CallbackQuery, state: FSMContext):
    """Handle date selection during edit."""
    parts = callback.data.split("_")
    year, month, day = int(parts[3]), int(parts[4]), int(parts[5])
    selected_date = datetime(year, month, day)

    if selected_date.date() < datetime.utcnow().date():
        await callback.answer("Cannot select a past date!", show_alert=True)
        return

    await state.update_data(editing_selected_date=selected_date)
    await state.set_state(EditScheduleStates.editing_time)

    data = await state.get_data()
    schedule_id = data.get("editing_schedule_id")

    await callback.message.edit_text(
        f"🕐 <b>Edit Time for Schedule #{schedule_id}</b>\n\n"
        f"<b>Date:</b> {selected_date.strftime('%b %d, %Y')}\n\n"
        f"Select time:",
        reply_markup=create_time_picker(),
        parse_mode="HTML"
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("edit_time_hour_"), EditScheduleStates.editing_time)
async def handle_edit_time_hour(callback: types.CallbackQuery, state: FSMContext):
    """Handle time selection during edit."""
    hour = int(callback.data.split("_")[3])
    data = await state.get_data()
    selected_date = data.get("editing_selected_date")
    schedule_id = data.get("editing_schedule_id")

    if not selected_date or not schedule_id:
        await callback.answer("Error: Missing data", show_alert=True)
        await state.clear()
        return

    next_run = selected_date.replace(hour=hour, minute=0, second=0, microsecond=0)

    if next_run <= datetime.utcnow():
        await callback.answer("Cannot schedule in the past!", show_alert=True)
        return

    async with AsyncSessionLocal() as session:
        values = {"next_run": next_run}
        if data.get("editing_new_type"):
            values["type"] = data["editing_new_type"]
            values["cron_expr"] = None  # Clear cron if switching to fixed time

        await session.execute(
            update(Schedule).where(Schedule.id == schedule_id).values(**values)
        )
        await session.commit()
        
        result = await session.execute(
            select(Schedule).options(selectinload(Schedule.batches)).where(Schedule.id == schedule_id)
        )
        sched = result.scalar_one()

    await state.clear()
    
    logger.info(f"Schedule #{schedule_id} time updated to {next_run} by admin {callback.from_user.id}")

    await callback.message.edit_text(
        f"✅ <b>Time Updated!</b>\n\n"
        f"📅 <b>Schedule #{sched.id}</b>\n"
        f"<b>New Time:</b> <code>{format_12hour(next_run)}</code>\n"
        f"<b>Type:</b> {sched.type.value.title()}",
        reply_markup=get_schedule_actions_keyboard(sched.id, sched.is_active),
        parse_mode="HTML"
    )
    await callback.answer()


# ----------------------------------------------------------------------
# Edit Batches Flow
# ----------------------------------------------------------------------
@dp.callback_query(F.data.startswith("edit_batches_"))
async def handle_edit_batches_start(callback: types.CallbackQuery, state: FSMContext):
    """Start editing schedule batches."""
    if not await ensure_user_exists(callback.from_user.id):
        await callback.answer("No permission.", show_alert=True)
        return

    schedule_id = int(callback.data.split("_")[2])
    
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Schedule).options(selectinload(Schedule.batches)).where(Schedule.id == schedule_id)
        )
        sched = result.scalar_one_or_none()
        
        if not sched:
            await callback.answer("Schedule not found!", show_alert=True)
            return
        
        all_batches = (await session.execute(select(Batch))).scalars().all()
        current_batch_ids = [b.id for b in sched.batches]

    await state.update_data(
        editing_schedule_id=schedule_id, 
        editing_batch_ids=current_batch_ids.copy()
    )
    await state.set_state(EditScheduleStates.editing_batches)

    await callback.message.edit_text(
        f"📦 <b>Edit Batches for Schedule #{schedule_id}</b>\n\n"
        f"Select/deselect batches:",
        reply_markup=get_edit_batch_keyboard(all_batches, current_batch_ids, schedule_id),
        parse_mode="HTML"
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("edit_batch_sel_"))
async def handle_edit_batch_toggle(callback: types.CallbackQuery, state: FSMContext):
    """Toggle batch selection during edit."""
    parts = callback.data.split("_")
    schedule_id = int(parts[3])
    batch_id = int(parts[4])
    
    data = await state.get_data()
    selected = data.get("editing_batch_ids", [])
    
    if batch_id in selected:
        selected.remove(batch_id)
    else:
        selected.append(batch_id)
    
    await state.update_data(editing_batch_ids=selected)

    async with AsyncSessionLocal() as session:
        all_batches = (await session.execute(select(Batch))).scalars().all()

    await callback.message.edit_reply_markup(
        reply_markup=get_edit_batch_keyboard(all_batches, selected, schedule_id)
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("edit_batch_save_"))
async def handle_edit_batch_save(callback: types.CallbackQuery, state: FSMContext):
    """Save batch changes."""
    schedule_id = int(callback.data.split("_")[3])
    data = await state.get_data()
    selected_batch_ids = data.get("editing_batch_ids", [])

    if not selected_batch_ids:
        await callback.answer("Please select at least one batch!", show_alert=True)
        return

    async with AsyncSessionLocal() as session:
        # Remove existing associations
        await session.execute(
            delete(schedule_batch_association).where(
                schedule_batch_association.c.schedule_id == schedule_id
            )
        )
        
        # Add new associations
        for bid in selected_batch_ids:
            await session.execute(
                schedule_batch_association.insert().values(schedule_id=schedule_id, batch_id=bid)
            )
        
        await session.commit()
        
        result = await session.execute(
            select(Schedule).options(selectinload(Schedule.batches)).where(Schedule.id == schedule_id)
        )
        sched = result.scalar_one()

    await state.clear()
    
    logger.info(f"Schedule #{schedule_id} batches updated by admin {callback.from_user.id}")

    batches = ", ".join(b.name for b in sched.batches)
    
    await callback.message.edit_text(
        f"✅ <b>Batches Updated!</b>\n\n"
        f"📅 <b>Schedule #{sched.id}</b>\n"
        f"<b>New Batches:</b> {batches}",
        reply_markup=get_schedule_actions_keyboard(sched.id, sched.is_active),
        parse_mode="HTML"
    )
    await callback.answer()


# ----------------------------------------------------------------------
# Delete Flow with Confirmation
# ----------------------------------------------------------------------
@dp.callback_query(F.data.startswith("sched_delete_"))
async def handle_delete_confirmation(callback: types.CallbackQuery, state: FSMContext):
    """Show delete confirmation dialog."""
    if not await ensure_user_exists(callback.from_user.id):
        await callback.answer("No permission.", show_alert=True)
        return

    schedule_id = int(callback.data.split("_")[2])
    
    async with AsyncSessionLocal() as session:
        sched = await session.get(Schedule, schedule_id)
        if not sched:
            await callback.answer("Schedule not found!", show_alert=True)
            return

    await callback.message.edit_text(
        f"⚠️ <b>Delete Schedule #{schedule_id}?</b>\n\n"
        f"<b>This action cannot be undone!</b>\n\n"
        f"The schedule will be permanently deleted along with all its settings.",
        reply_markup=get_confirm_delete_keyboard(schedule_id),
        parse_mode="HTML"
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("sched_confirm_del_"))
async def handle_confirm_delete(callback: types.CallbackQuery, state: FSMContext):
    """Permanently delete a schedule."""
    if not await ensure_user_exists(callback.from_user.id):
        await callback.answer("No permission.", show_alert=True)
        return

    schedule_id = int(callback.data.split("_")[3])
    
    async with AsyncSessionLocal() as session:
        # Delete associations first
        await session.execute(
            delete(schedule_batch_association).where(
                schedule_batch_association.c.schedule_id == schedule_id
            )
        )
        # Delete schedule
        await session.execute(delete(Schedule).where(Schedule.id == schedule_id))
        await session.commit()

    logger.info(f"Schedule #{schedule_id} DELETED by admin {callback.from_user.id}")

    await callback.answer(f"Schedule #{schedule_id} deleted!", show_alert=True)
    
    # Go back to list
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Schedule).options(selectinload(Schedule.batches)).order_by(Schedule.id.desc())
        )
        schedules = result.scalars().all()

    if not schedules:
        await callback.message.edit_text(
            "📭 <b>No schedules remaining.</b>\n\n"
            "Use /schedule to create a new scheduled broadcast.",
            parse_mode="HTML"
        )
        return

    await callback.message.edit_text(
        f"📋 <b>Schedule Management</b>\n\n"
        f"Total: <code>{len(schedules)}</code> schedule(s)\n"
        f"Active: <code>{sum(1 for s in schedules if s.is_active)}</code> | "
        f"Paused: <code>{sum(1 for s in schedules if not s.is_active)}</code>\n\n"
        f"Select a schedule to manage:",
        reply_markup=get_schedule_list_keyboard(schedules, page=0),
        parse_mode="HTML"
    )



# ----------------------------------------------------------------------
# Edit Type Flow
# ----------------------------------------------------------------------
@dp.callback_query(F.data.startswith("edit_type_"))
async def handle_edit_type_start(callback: types.CallbackQuery, state: FSMContext):
    """Start editing schedule type."""
    if not await ensure_user_exists(callback.from_user.id):
        await callback.answer("No permission.", show_alert=True)
        return

    schedule_id = int(callback.data.split("_")[2])
    
    async with AsyncSessionLocal() as session:
        sched = await session.get(Schedule, schedule_id)
        if not sched:
            await callback.answer("Schedule not found!", show_alert=True)
            return

    await state.update_data(editing_schedule_id=schedule_id)
    await state.set_state(EditScheduleStates.editing_type)

    await callback.message.edit_text(
        f"📅 <b>Edit Type for Schedule #{schedule_id}</b>\n\n"
        f"Current Type: <b>{sched.type.value.title()}</b>\n\n"
        f"Select new schedule type:",
        reply_markup=get_schedule_type_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()


@dp.message(EditScheduleStates.editing_cron)
async def process_edit_cron(message: types.Message, state: FSMContext):
    """Process new cron expression."""
    if not await ensure_user_exists(message.from_user.id):
        await message.answer("No permission.")
        return

    data = await state.get_data()
    schedule_id = data.get("editing_schedule_id")
    new_type = data.get("editing_new_type")

    if not schedule_id or new_type != ScheduleType.CUSTOM:
        await message.answer("Error: Invalid state.")
        await state.clear()
        return

    # Validate cron
    import croniter
    try:
        cron = croniter.croniter(message.text.strip(), datetime.utcnow())
        next_run = cron.get_next(datetime)
    except Exception as e:
        await message.answer(
            f"❌ <b>Invalid Cron Expression</b>\n\nChecking: <code>{message.text}</code>\nError: {e}\n\n"
            "Please try again or click /cancel.",
            parse_mode="HTML"
        )
        return

    async with AsyncSessionLocal() as session:
        await session.execute(
            update(Schedule).where(Schedule.id == schedule_id).values(
                type=new_type,
                cron_expr=message.text.strip(),
                next_run=next_run
            )
        )
        await session.commit()
        
        result = await session.execute(
            select(Schedule).options(selectinload(Schedule.batches)).where(Schedule.id == schedule_id)
        )
        sched = result.scalar_one()

    await state.clear()
    
    logger.info(f"Schedule #{schedule_id} type updated to CUSTOM ({message.text}) by {message.from_user.id}")

    await message.answer(
        f"✅ <b>Schedule Updated!</b>\n\n"
        f"📅 <b>Schedule #{sched.id}</b>\n"
        f"<b>Type:</b> Custom\n"
        f"<b>Cron:</b> <code>{sched.cron_expr}</code>\n"
        f"<b>Next Run:</b> <code>{format_12hour(sched.next_run)}</code>",
        reply_markup=get_schedule_actions_keyboard(sched.id, sched.is_active),
        parse_mode="HTML"
    )


# ==============================================================================
# LEGACY COMMAND HANDLERS (kept for backward compatibility)
# ==============================================================================

@dp.message(Command("pause_schedule"))
async def cmd_pause_schedule(message: types.Message):
    """Pause a schedule by ID (legacy command)."""
    if not await ensure_user_exists(message.from_user.id): 
        return await message.answer("No permission.")
    try:
        sched_id = int(message.text.split(maxsplit=1)[1])
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(Schedule).where(Schedule.id == sched_id))
            sched = result.scalar_one_or_none()
            if not sched:
                await message.answer(f"Schedule #{sched_id} not found.")
                return
            await session.execute(update(Schedule).where(Schedule.id == sched_id).values(is_active=False))
            await session.commit()
        logger.info(f"Schedule #{sched_id} paused by admin {message.from_user.id}")
        await message.answer(f"⏸️ Schedule <b>#{sched_id}</b> paused.", parse_mode="HTML")
    except (IndexError, ValueError):
        await message.answer("Usage: <code>/pause_schedule &lt;id&gt;</code>", parse_mode="HTML")
    except Exception as e:
        logger.error(f"Error pausing schedule: {e}")
        await message.answer("An error occurred.")


@dp.message(Command("resume_schedule"))
async def cmd_resume_schedule(message: types.Message):
    """Resume a schedule by ID (legacy command)."""
    if not await ensure_user_exists(message.from_user.id): 
        return await message.answer("No permission.")
    try:
        sched_id = int(message.text.split(maxsplit=1)[1])
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(Schedule).where(Schedule.id == sched_id))
            sched = result.scalar_one_or_none()
            if not sched:
                await message.answer(f"Schedule #{sched_id} not found.")
                return
            await session.execute(update(Schedule).where(Schedule.id == sched_id).values(is_active=True))
            await session.commit()
        logger.info(f"Schedule #{sched_id} resumed by admin {message.from_user.id}")
        await message.answer(f"▶️ Schedule <b>#{sched_id}</b> resumed.", parse_mode="HTML")
    except (IndexError, ValueError):
        await message.answer("Usage: <code>/resume_schedule &lt;id&gt;</code>", parse_mode="HTML")
    except Exception as e:
        logger.error(f"Error resuming schedule: {e}")
        await message.answer("An error occurred.")


@dp.message(Command("delete_schedule"))
async def cmd_delete_schedule(message: types.Message):
    """Delete a schedule by ID (legacy command)."""
    if not await ensure_user_exists(message.from_user.id): 
        return await message.answer("No permission.")
    try:
        sched_id = int(message.text.split(maxsplit=1)[1])
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(Schedule).where(Schedule.id == sched_id))
            sched = result.scalar_one_or_none()
            if not sched:
                await message.answer(f"Schedule #{sched_id} not found.")
                return
            await session.execute(
                delete(schedule_batch_association).where(
                    schedule_batch_association.c.schedule_id == sched_id
                )
            )
            await session.execute(delete(Schedule).where(Schedule.id == sched_id))
            await session.commit()
        logger.info(f"Schedule #{sched_id} DELETED by admin {message.from_user.id}")
        await message.answer(f"🗑️ Schedule <b>#{sched_id}</b> deleted permanently.", parse_mode="HTML")
    except (IndexError, ValueError):
        await message.answer("Usage: <code>/delete_schedule &lt;id&gt;</code>", parse_mode="HTML")
    except Exception as e:
        logger.error(f"Error deleting schedule: {e}")
        await message.answer("An error occurred.")